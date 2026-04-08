"""
=============================================================================
File: agent.py
Capabilities:
1. Agent Definition: Defines the core 'SheetDataScienceAgent'.
2. Tool Binding: Connects the agent directly to our modular ADK tool wrappers.
=============================================================================
"""

import logging
import os
from google.adk.agents import Agent

# Import our ADK tool wrappers, including the restored SQL bridge tool
from .tools import (
    list_drive_folder, 
    download_drive_file, 
    sheet_nl2sql,         # <-- The Natural Language to SQL bridge
    execute_sql_on_file, 
    upload_to_drive
)
from .prompts import return_instructions_sheet

try:
    from .config import get_logger
    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

# Add tools to the Agent directly
root_agent = Agent(
    name="SheetDataScienceAgent",
    model="gemini-2.5-flash", 
    description="An enterprise agent that analyzes and transforms Google Drive spreadsheet data (Excel/CSV) using DuckDB SQL.",
    instruction=return_instructions_sheet(),
    tools=[
        list_drive_folder,
        download_drive_file, 
        sheet_nl2sql,         # <-- ADDED: Registered so the AI can use it
        execute_sql_on_file, 
        upload_to_drive
    ]
)

logger.info("SheetDataScienceAgent initialized and tools bound successfully.")