import sys
sys.path.append('backend')
import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config.agents import LLMType
from src.llms.llm import _get_env_llm_conf, load_yaml_config, _get_config_file_path, _get_llm_type_config_keys
from langchain_core.messages import HumanMessage

async def main():
    llm_type = "legacy"
    conf = load_yaml_config(_get_config_file_path())
    yaml_conf = conf.get(_get_llm_type_config_keys().get(llm_type), {})
    env_conf = _get_env_llm_conf(llm_type)
    merged_conf = {**yaml_conf, **env_conf}
    
    key_val = merged_conf.get("api_key", "")
    if not key_val:
        import os
        key_val = os.environ.get(f"{llm_type.upper()}_MODEL__API_KEY", 
                  os.environ.get("BASIC_MODEL__api_key", os.environ.get("GEMINI_API_KEY", "")))
                  
    raw_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=key_val, max_retries=0)
    print("Testing raw google API with max_retries=0...")
    try:
        res = await raw_llm.ainvoke([HumanMessage(content="Say hello")])
        print("Success:", res.content)
    except Exception as e:
        print("RAW ERROR TRACEBACK:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
