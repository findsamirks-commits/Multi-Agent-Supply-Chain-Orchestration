import streamlit as st
import sqlite3
import json
import os
from ddgs import DDGS
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# 1. Initialization
load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

st.set_page_config(page_title="Agentic Supply Chain", page_icon="🤖", layout="wide")
st.title("🤖 Multi-Agent Procurement Squad")
st.markdown("Autonomous LangGraph orchestration for inventory monitoring and vendor negotiation.")

class ProcurementState(TypedDict):
    sku: str
    stock_status: str
    competitor_price: float
    target_cost: float
    vendor_email: str

# 2. Agent Definitions (Adapted for Streamlit UI)
def inventory_analyst(state: ProcurementState):
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("SELECT stock_units, avg_daily_sales FROM stock WHERE sku = ?", (state['sku'],))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        stock_units, avg_daily_sales = result
        days_of_cover = stock_units / avg_daily_sales if avg_daily_sales > 0 else 999
        status_string = f"{stock_units} units remaining ({days_of_cover:.1f} days of cover)"
        
        if days_of_cover <= 3.0:
            state["stock_status"] = "CRITICAL: " + status_string
        else:
            state["stock_status"] = "HEALTHY: " + status_string
    else:
        state["stock_status"] = "UNKNOWN: SKU not found."
    return state

def competitor_intel(state: ProcurementState):
    query = f"{state['sku']} price online BigBasket Zepto"
    try:
        raw_results = list(DDGS().text(query, max_results=3))
        search_results = str(raw_results)
    except Exception:
        search_results = "No results found."
        
    prompt = f"""
    Analyze these web search results for the product '{state['sku']}':
    {search_results}
    Find the current selling price in INR (₹). If multiple prices exist, extract the lowest one.
    Output ONLY a valid JSON object: {{"competitor_price": float, "target_cost": float (which is price * 0.85)}}
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        clean_text = response.content.replace('```json', '').replace('```', '').strip()
        pricing_data = json.loads(clean_text)
        state["competitor_price"] = round(pricing_data.get("competitor_price", 0.0), 2)
        state["target_cost"] = round(pricing_data.get("target_cost", 0.0), 2)
    except:
        state["competitor_price"] = 0.0
        state["target_cost"] = 0.0
    return state

def procurement_manager(state: ProcurementState):
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

def route_based_on_stock(state: ProcurementState):
    if "CRITICAL" in state["stock_status"]:
        return "intel"
    return END

# 3. Build Graph
workflow = StateGraph(ProcurementState)
workflow.add_node("analyst", inventory_analyst)
workflow.add_node("intel", competitor_intel)
workflow.add_node("manager", procurement_manager)
workflow.set_entry_point("analyst")
workflow.add_conditional_edges("analyst", route_based_on_stock, {"intel": "intel", END: END})
workflow.add_edge("intel", "manager")
workflow.add_edge("manager", END)
app = workflow.compile()

# 4. Streamlit UI
sku_choice = st.selectbox("Select SKU to Analyze:", [
    "Aashirvaad Whole Wheat Atta 5kg", 
    "Amul Taaza Milk 1L", 
    "Tata Salt 1kg"
])

if st.button("Run Procurement Squad"):
    with st.spinner("Agents are analyzing inventory and market data..."):
        final_state = app.invoke({"sku": sku_choice})
        
    st.subheader("📊 Agent Telemetry")
    col1, col2, col3 = st.columns(3)
    col1.metric("Inventory Status", final_state.get("stock_status", "N/A").split(":")[0])
    col2.metric("Competitor Lowest Price", f"₹{final_state.get('competitor_price', 0.0)}")
    col3.metric("Required Target Cost", f"₹{final_state.get('target_cost', 0.0)}")
    
    st.divider()
    
    if "HEALTHY" in final_state.get("stock_status", ""):
        st.success("✅ Stock is healthy. No procurement negotiation required at this time.")
    else:
        st.subheader("✍️ Drafted Vendor Negotiation")
        st.text_area("Email Draft", final_state.get("vendor_email", ""), height=300)