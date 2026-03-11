## LLM Usage Log

This project was developed with an AI-first philosophy, leveraging ChatGPT and Copilot to accelerate development and ensure clean, professional code.

### Tools Used
- **ChatGPT (OpenAI)** – assisted in writing:
  - Streamlit dashboard layout and structure
  - DuckDB queries for telemetry data ingestion
  - Human-readable metrics formatting (Total Duration)
  - Helper functions for column detection and role/email mapping
  - Predefined SQL queries for analytics and insights

### Example Prompts & Outputs
1. **Prompt:**  
   *"Generate a Streamlit dashboard that shows total events, total tokens, and a line chart of events over time from a DuckDB database."*  

   **Output:**  
   - Python code skeleton with columns for metrics and line chart visualization.  
   - Included error handling and optional token summation.

2. **Prompt:**  
   *"Convert timestamp differences into a human-readable duration including years, months, days, hours, and minutes."*  

   **Output:**  
   - Python function computing `years, months, days, hours, minutes` from a pandas timedelta.  
   - Safe handling of negative months/days.

### Validation of AI-Generated Code
- Each AI-generated function and snippet was **tested against the Claude telemetry dataset**.  
- Metrics were verified manually and visually against known values (e.g., total events, duration).  
- Queries were run in DuckDB to ensure correct aggregation and outputs.  
- Minor adaptations were applied to match dataset column names (`ts`, `user_email`, `output_tokens`, etc.).