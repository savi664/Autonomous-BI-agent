from typing import TypedDict, Any 

class AgentState(TypedDict):
    """
    Represents the state of an agent, including its name, description, and any additional attributes.
    """
    dataset: Any
    dataset_profile:dict
    dataset_path: str
    hypotheses:list
    code:str
    report:str
    execution_result:dict
