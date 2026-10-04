import os
import sqlite3
import json
from duckduckgo_search import DDGS
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Initialize the LLM router using the secure API key and updated model
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

# 1. Define the State that agents will pass around
class ProcurementState(TypedDict):
    sku: str
    stock_status: str
    competitor_price: float
    target_cost: float
    vendor_email: str

# 2. Define the Node Functions (Our Agents)
def inventory_analyst(state: ProcurementState):
    print(f"🔍 Analyst querying local SQLite database for: {state['sku']}")
    
    # Connect to the local database
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Fetch real stock data
    cursor.execute("SELECT stock_units, avg_daily_sales FROM stock WHERE sku = ?", (state['sku'],))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        stock_units, avg_daily_sales = result
        days_of_cover = stock_units / avg_daily_sales if avg_daily_sales > 0 else 999
        
        status_string = f"{stock_units} units remaining ({days_of_cover:.1f} days of cover)"
        
        # Apply business logic threshold
        if days_of_cover <= 3.0:
            state["stock_status"] = "CRITICAL: " + status_string
        else:
            state["stock_status"] = "HEALTHY: " + status_string
    else:
        state["stock_status"] = "UNKNOWN: SKU not found in database."
        
    print(f"📊 Stock Status Found: {state['stock_status']}")
    return state

# Initialize the search tool
def competitor_intel(state: ProcurementState):
    print(f"🕵️ Intel searching live competitor prices for: {state['sku']}")
    
    # Query specific quick-commerce rivals
    query = f"{state['sku']} price online BigBasket Zepto"
    
    raw_results = list(DDGS().text(query, max_results=3))
    print(f"🔍 Raw snippets found: {len(raw_results)}")
    
    # Use native DDGS directly, bypassing LangChain's broken wrapper
    raw_results = DDGS().text(query, max_results=3)
    search_results = str(raw_results)
    
    # Prompt Gemini to parse the messy search results into structured JSON
    prompt = f"""
    Analyze these web search results for the product '{state['sku']}':
    {search_results}
    
    Find the current selling price in INR (₹). If multiple prices exist, extract the lowest one.
    Output ONLY a valid JSON object with exactly two keys. Do not include markdown formatting or extra text.
    {{
        "competitor_price": (float value of the lowest price found, or 0.0 if none found),
        "target_cost": (competitor_price * 0.85) 
    }}
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        # Clean up markdown formatting if the LLM includes it and parse
        clean_text = response.content.replace('```json', '').replace('```', '').strip()
        pricing_data = json.loads(clean_text)
        state["competitor_price"] = round(pricing_data.get("competitor_price", 0.0), 2)
        state["target_cost"] = round(pricing_data.get("target_cost", 0.0), 2)
    except Exception as e:
        print(f"⚠️ Pricing parse error. Defaulting to 0.0.")
        state["competitor_price"] = 0.0
        state["target_cost"] = 0.0
        
    print(f"💰 Market Price: ₹{state['competitor_price']} | Required Target Cost: ₹{state['target_cost']}")
    return state

def procurement_manager(state: ProcurementState):
    print("✍️ Manager drafting vendor negotiation...")
    prompt = f"""
    You are the Category Head at Milkbasket.
    SKU: {state['sku']}
    Stock: {state['stock_status']}
    Competitor Price: ₹{state['competitor_price']}
    Target Cost: ₹{state['target_cost']}
    
    Write a brief, firm negotiation email to the vendor requesting a price drop to meet our target cost, citing competitor retail prices and our urgent restocking need.
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    state["vendor_email"] = response.content
    return state
# 3. Define Conditional Routing Logic
def route_based_on_stock(state: ProcurementState):
    if "CRITICAL" in state["stock_status"]:
        print("🚨 Critical stock detected. Routing to Competitor Intel...")
        return "intel"
    else:
        print("✅ Stock is healthy. Terminating workflow.")
        return END

# 4. Build and Compile Graph with Checkpointing & Breakpoints
memory = MemorySaver()

workflow = StateGraph(ProcurementState)

workflow.add_node("analyst", inventory_analyst)
workflow.add_node("intel", competitor_intel)
workflow.add_node("manager", procurement_manager)

workflow.set_entry_point("analyst")

workflow.add_conditional_edges(
    "analyst",
    route_based_on_stock,
    {
        "intel": "intel",
        END: END
    }
)

workflow.add_edge("intel", "manager")
workflow.add_edge("manager", END)

# Interrupt graph execution before the manager node runs
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["manager"]
)

# 5. Interactive Execution Loop
if __name__ == "__main__":
    thread_config = {"configurable": {"thread_id": "procurement_po_101"}}
    initial_state = {"sku": "Amul Taaza Milk 1L"}

    print("🚀 Initiating autonomous squad workflow...\n")
    app.invoke(initial_state, config=thread_config)

    # Inspect current state at the breakpoint
    current_snapshot = app.get_state(thread_config)

    if current_snapshot.next and "manager" in current_snapshot.next:
        data = current_snapshot.values
        print("\n" + "=" * 50)
        print("🛑 HUMAN-IN-THE-LOOP APPROVAL REQUIRED")
        print("=" * 50)
        print(f"SKU              : {data.get('sku')}")
        print(f"Inventory Status : {data.get('stock_status')}")
        print(f"Competitor Price : ₹{data.get('competitor_price')}")
        print(f"Suggested Cost   : ₹{data.get('target_cost')}")
        print("-" * 50)

        user_choice = input("Approve target cost? Enter 'y' to proceed, or input a custom target cost (e.g. 42.50): ").strip()

        # Allow managerial override of landing cost
        if user_choice.lower() != 'y' and user_choice:
            try:
                new_target = float(user_choice)
                app.update_state(thread_config, {"target_cost": new_target})
                print(f"✏️ Target cost manually overridden to: ₹{new_target}")
            except ValueError:
                print("⚠️ Invalid numerical input. Proceeding with original target cost.")

        print("\n▶️ Resuming graph execution to Procurement Manager...")
        final_state = app.invoke(None, config=thread_config)

        if "vendor_email" in final_state:
            print("\n=== FINAL APPROVED VENDOR EMAIL ===")
            print(final_state["vendor_email"])