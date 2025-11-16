from typing import Any, Optional


def extract_input_from_kwargs(kwargs: dict[str, Any]) -> Optional[str]:
    """Extract the input text from OpenAI API kwargs.
    
    Args:
        kwargs: Keyword arguments being passed to the API
        
    Returns:
        The input text if present, None otherwise
    """
    input_value = kwargs.get("input")
    
    if isinstance(input_value, str):
        return input_value
    elif isinstance(input_value, list) and input_value and isinstance(input_value[0], str):
        return input_value[0]
    
    return None


def set_input_in_kwargs(kwargs: dict[str, Any], new_input: str) -> None:
    """Set the input in OpenAI API kwargs.
    
    Args:
        kwargs: Keyword arguments being passed to the API
        new_input: The new input text to set
    """
    if "input" in kwargs:
        if isinstance(kwargs["input"], list):
            kwargs["input"] = [new_input]
        else:
            kwargs["input"] = new_input


def get_output_text(response: Any) -> Optional[str]:
    """Extract output text from an OpenAI response.
    
    Args:
        response: The response object from OpenAI API
        
    Returns:
        The output text if available, None otherwise
    """
    if response is None:
        return None
    
    if hasattr(response, 'output_text'):
        return response.output_text
    
    if hasattr(response, 'text'):
        return response.text
    
    if hasattr(response, 'choices') and response.choices:
        first_choice = response.choices[0]
        if hasattr(first_choice, 'message') and hasattr(first_choice.message, 'content'):
            return first_choice.message.content
        elif hasattr(first_choice, 'text'):
            return first_choice.text
    
    if isinstance(response, dict):
        if 'output_text' in response:
            return response['output_text']
        elif 'text' in response:
            return response['text']
    
    return None


def set_output_text(response: Any, new_text: str) -> Any:
    """Set the output text in an OpenAI response.
    
    Args:
        response: The response object from OpenAI API
        new_text: The new output text
        
    Returns:
        The modified response object
    """
    if response is None:
        return response
    
    if hasattr(response, 'output_text'):
        try:
            response.output_text = new_text
        except AttributeError:
            pass
    
    if hasattr(response, 'text'):
        try:
            response.text = new_text
        except AttributeError:
            pass
    
    if hasattr(response, 'choices') and response.choices:
        first_choice = response.choices[0]
        if hasattr(first_choice, 'message') and hasattr(first_choice.message, 'content'):
            try:
                first_choice.message.content = new_text
            except AttributeError:
                pass
        elif hasattr(first_choice, 'text'):
            try:
                first_choice.text = new_text
            except AttributeError:
                pass
    
    if isinstance(response, dict):
        if 'output_text' in response:
            response['output_text'] = new_text
        elif 'text' in response:
            response['text'] = new_text
    
    return response
