# 🤖 Multi-Agent Procurement Squad

An autonomous supply chain orchestration system built with LangGraph, Streamlit, and Gemini 2.5 Flash. This architecture utilizes a decentralized graph of specialized AI agents to monitor inventory, gather competitive intelligence, and draft vendor negotiations.

## Agent Workflow
1. **Inventory Analyst**: Queries a local SQLite database to dynamically calculate SKU run-rates and days of cover, identifying critical stock-out risks.
2. **Conditional Router**: Evaluates the Analyst's state. Bypasses the LLM entirely if stock is healthy, conserving compute.
3. **Competitor Intel**: Uses the native DuckDuckGo search library to scrape real-time market pricing from rival quick-commerce platforms and calculates a 15% margin target cost.
4. **Procurement Manager**: Synthesizes the telemetry into a professional, data-backed vendor negotiation email requesting a price drop.

## Tech Stack
* **Orchestration**: LangGraph, LangChain
* **LLM**: Google Gemini 2.5 Flash
* **Interface**: Streamlit
* **Tools**: SQLite3, DuckDuckGo Search
