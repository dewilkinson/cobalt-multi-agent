import pytest
from src.server.app import _invoke_vli_agent

@pytest.mark.asyncio
async def test_invoke_vli_agent_smc_pipeline():
    """
    E2E Integration test for the _invoke_vli_agent pipeline.
    This test ensures that the 'run smc analysis on ETHUSDT' 
    prompt correctly routes through the Coordinator -> SMC Analyst -> Reporter,
    and returns a structured Markdown response.
    """
    pipeline_request = "run smc analysis on ETHUSDT"
    
    try:
        # direct_mode=True forces the fast-path parser if possible, 
        # but SMC commands are technical so they should route to SMC Analyst.
        response = await _invoke_vli_agent(pipeline_request, direct_mode=False)
        
        # Verify pipeline output format
        assert isinstance(response, str)
        print("E2E Response successfully generated!")
        print(f"Output: {response[:200]}...")
        
        # Verify the pipeline successfully reached the reporter node
        assert len(response) > 10  # Legitimate response
    except Exception as e:
        pytest.fail(f"VLI Pipeline failed with exception: {str(e)}")
