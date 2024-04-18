from langchain.agents import  Tool
from langchain_community.llms import OpenAI
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine
#from tkinter import *
from langchain.agents import Tool, create_openai_functions_agent, AgentExecutor
from langchain.sql_database import SQLDatabase
from langchain_experimental.tools import PythonREPLTool
from langchain.memory import ConversationBufferMemory
import os
import pysnow, openai
from langchain.agents import tool
import streamlit as st
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from azure.storage.blob import BlobServiceClient, BlobClient


from dotenv import load_dotenv
openai.api_key = os.getenv("OPENAI_API_KEY")
CONN_STR = os.getenv("BLOB_CONN_STRING")

# # Connection with db
# os.environ["SQL_SERVER_USERNAME"] = "sqlserver"
# os.environ["SQL_SERVER_ENDPOINT"] = "chatbotserver456"
# os.environ["SQL_SERVER_PASSWORD"] = "chatbot@123"  
# os.environ["SQL_SERVER_DATABASE"] = "chatdb"
# Connection with db
# os.environ["SQL_SERVER_USERNAME"] = os.getenv("SQL_SERVER_USERNAME")
# os.environ["SQL_SERVER_ENDPOINT"] = os.getenv("SQL_SERVER_ENDPOINT")
# os.environ["SQL_SERVER_PASSWORD"] = os.getenv("SQL_SERVER_PASSWORD")
# os.environ["SQL_SERVER_DATABASE"] = os.getenv("SQL_SERVER_DATABASE")

SQL_SERVER_USERNAME = "sqlserver"
SQL_SERVER_ENDPOINT = "chatbotserver456" 
SQL_SERVER_PASSWORD = "chatbot@123" 
SQL_SERVER_DATABASE = "chatdb"

load_dotenv()

st.set_page_config(
    page_title="MagicLQ",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)



# Initialize a BlobServiceClient
connection_string = CONN_STR
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

# Access the container
container_name = "logdata"
container_client = blob_service_client.get_container_client(container_name)

# Access the blob
blob_name = "dbo.Logs.csv"
blob_client = container_client.get_blob_client(blob_name)

# Download the blob to a local file
with open("dbo.Logs.csv", "wb") as download_file:
    download_file.write(blob_client.download_blob().readall())

llm = ChatOpenAI(temperature=0, model="gpt-4", streaming=True)



# db driver selection and setup
driver = '{ODBC Driver 18 for SQL Server}'
odbc_str = 'mssql+pyodbc:///?odbc_connect=' \
                'Driver='+driver+ \
                ';Server=tcp:' + SQL_SERVER_ENDPOINT+'.database.windows.net;PORT=1433' + \
                ';DATABASE=' + SQL_SERVER_DATABASE + \
                ';Uid=' + SQL_SERVER_USERNAME+ \
                ';Pwd=' + SQL_SERVER_PASSWORD + \
                ';Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

db_engine = create_engine(odbc_str)
db = SQLDatabase(db_engine)
db_chain = SQLDatabaseChain.from_llm(llm, db, verbose=True, top_k=10)


@tool
def create_servicenow_ticket (incident_str):
    """Creating Service Now ticket ."""
    
    # Create client object
    c = pysnow.Client(instance='dev217121', user='admin', password='Hello@World123')

    # Define a resource, here we'll use the incident table API
    incident = c.resource(api_path='/table/incident')

    # Set the payload
    new_record = {
        'short_description': incident_str,
        'description': incident_str
    }

    # Create a new incident record
    result = incident.create(payload=new_record)
    incident_number = result.one()['number']

    return incident_number



tools= [
       Tool(
        name="Log-DB", 
        func=db_chain.run,
        description="useful for when you need to answer questions about Logs and the content of Logs. Input should be in the form of a question containing full context.",
    ),
       create_servicenow_ticket,PythonREPLTool()
]

prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", """You are a chatbot having a conversation with a human.
                     You have the following tools to use:
 
 Log-DB: useful for when you need to answer questions about Logs and the content of Logs.
        Use this tool to create a table.
 
 create_servicenow_ticket: Use this when the user says "Create servicenow ticket for <error description by the user>
 
 PythonREPLTool: Use this to plot a graph or a chart. First you rephrase the user input so that a Python code generator can understand it.
            You have access to python REPL, which you can use to execute python code.
                     Skip bad lines, blank lines while reading the file if any.
            Generate python code to answer the user input based on the dbo.Logs.csv file which has the columns: 
            
                    GUID - a unique ID for all the rows
                    TimeStamp - this column is in the UTC format, always do the necessary datetime conversion when required
                     SourceSystem - These could be "IIS", "MuleSoft", "Tomcat", "Nginx", "Mainframe" and "WebLogic"
                     SourceApplication - Applications under each source system
                     SourceModule - Modules under each source application
                     Type - these are "Info", "Error" and "Warning"
                     Tags
                     Description
                     
            If the user asks you to plot a graph, get the data you need for it, generate and save the image as graph.png.
            
            If you get an error, debug your code and try again.
            Only use the output of your code to answer the question.
            You might know the answer without running any code, but you should still run the code to get the answer.Use this to chat with the user regarding customer survey data.
 --------
 
 """),
                    MessagesPlaceholder("history", optional=True),
                    ("human", "{input}"),
                    MessagesPlaceholder("agent_scratchpad"),
                ]
            )

agent = create_openai_functions_agent(llm, tools=tools, prompt=prompt)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


import time
import re

def stream_data(output):
    for word in re.split(r'(\s+)', output):
        yield word + " "
        time.sleep(0.08)

avatar_image = "Magicappicon.png"
user_image = "usericon.png"


memory = ConversationBufferMemory(llm=llm,memory_key='history', return_messages=True, output_key='output')


starter_message = "How can I help you?"
if "messages" not in st.session_state or st.sidebar.button("Clear message history"):
    st.session_state["messages"] = [AIMessage(content=starter_message)]
    
    
for msg in st.session_state.messages:
    if isinstance(msg, AIMessage):
        st.chat_message("assistant", avatar=avatar_image).write(msg.content)
    elif isinstance(msg, HumanMessage):
        st.chat_message("user", avatar=user_image).write(msg.content)
    memory.chat_memory.add_message(msg)
    
st.cache_resource(ttl="2h")   
def chatbot():
    if prompt := st.chat_input(placeholder=starter_message):
        st.chat_message("user", avatar=user_image).write(prompt)
        with st.chat_message("assistant", avatar=avatar_image):
            with st.spinner("Thinking..."):
                st_callback = StreamlitCallbackHandler(st.container())
                response = agent_executor(
                    {"input": prompt, "history": st.session_state.messages},
                    #callbacks=[st_callback],
                    include_run_info=True,
                )
                st.session_state.messages.append(AIMessage(content=response["output"]))
                st.write_stream(stream_data(response["output"]))
                if os.path.exists('graph.png'):  
                    st.image("graph.png")   
                memory.save_context({"input": prompt}, response)
                if os.path.exists('graph.png'):
                    os.remove('graph.png')
                st.session_state["messages"] = memory.buffer
                run_id = response["__run"].run_id

chatbot()
        
        
        
        
