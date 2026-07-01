from typing import TypedDict, Any 

class AgentState(TypedDict):
    """
    Represents the state of an agent, including its name, description, and any additional attributes.
    """
    dataset_profile:dict
    hypotheses:list
    code:str
    report:str
    execution_result:dict
