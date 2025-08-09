"""
JSON parser module for formatting and validating client requests.
Handles JSON string parsing and request formatting for the Schwab API server.
"""
import json
import logging
import os
from typing import Dict, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class JSONRequestParser:
    """Parser for JSON request strings and formatting for server communication."""
    
    # Valid actions that the server accepts
    VALID_ACTIONS = {
        'ping',
        'test_connection',
        'initialize_credentials',
        'get_linked_accounts',
        'get_account_details',
        'get_account_summary',
        'get_positions',
        'get_positions_by_symbol',
        'get_quotes',
        'get_option_chains',
        'place_stock_order',
        'cancel_stock_order',
        'replace_stock_order',
        'get_stock_order_details',
        'get_stock_orders',
        'place_option_order',
        'cancel_option_order',
        'replace_option_order',
        'get_option_order_details',
        'get_option_orders'
    }
    
    # Required parameters for each action
    REQUIRED_PARAMS = {
        'initialize_credentials': ['app_key', 'app_secret'],
        'get_positions_by_symbol': ['symbol'],
        'get_quotes': ['symbols'],
        'get_option_chains': ['symbol']
    }
    
    # Optional parameters for each action
    OPTIONAL_PARAMS = {
        'initialize_credentials': ['callback_url', 'tokens_file'],
        'get_account_details': ['account_hash', 'include_positions'],
        'get_account_summary': ['account_hash'],
        'get_positions': ['account_hash'],
        'get_positions_by_symbol': ['account_hash'],
        'get_quotes': ['fields', 'indicative', 'use_streaming'],
        'get_option_chains': ['contractType', 'strike', 'fromDate', 'toDate', 'use_streaming']
    }
    
    def __init__(self):
        """Initialize the JSON parser."""
        pass
    
    def parse_json_string(self, json_string: str) -> Dict[str, Any]:
        """
        Parse a JSON string into a dictionary.
        
        Args:
            json_string: JSON string to parse
            
        Returns:
            Dict containing parsed JSON or error information
        """
        try:
            if not json_string or not json_string.strip():
                return {
                    'success': False,
                    'error': 'Empty JSON string provided',
                    'timestamp': datetime.now().isoformat()
                }
            
            parsed_data = json.loads(json_string.strip())
            
            if not isinstance(parsed_data, dict):
                return {
                    'success': False,
                    'error': 'JSON must be an object/dictionary, not array or primitive',
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'success': True,
                'data': parsed_data,
                'timestamp': datetime.now().isoformat()
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            return {
                'success': False,
                'error': f'Invalid JSON format: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {str(e)}")
            return {
                'success': False,
                'error': f'Error parsing JSON: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def validate_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a request dictionary for required fields and format.
        
        Args:
            request_data: Dictionary containing request data
            
        Returns:
            Dict containing validation result
        """
        try:
            # Check if action is present
            if 'action' not in request_data:
                return {
                    'success': False,
                    'error': 'Missing required field: action',
                    'timestamp': datetime.now().isoformat()
                }
            
            action = request_data['action'].lower()
            
            # Check if action is valid
            if action not in self.VALID_ACTIONS:
                return {
                    'success': False,
                    'error': f'Invalid action: {action}',
                    'valid_actions': list(self.VALID_ACTIONS),
                    'timestamp': datetime.now().isoformat()
                }
            
            # Check required parameters
            if action in self.REQUIRED_PARAMS:
                for param in self.REQUIRED_PARAMS[action]:
                    if param not in request_data:
                        return {
                            'success': False,
                            'error': f'Missing required parameter for {action}: {param}',
                            'required_params': self.REQUIRED_PARAMS[action],
                            'timestamp': datetime.now().isoformat()
                        }
                    
                    # Check for empty required parameters
                    if not request_data[param] or str(request_data[param]).strip() == '':
                        return {
                            'success': False,
                            'error': f'Required parameter cannot be empty: {param}',
                            'timestamp': datetime.now().isoformat()
                        }
            
            # Validate specific parameter types and values
            validation_result = self._validate_specific_params(action, request_data)
            if not validation_result['success']:
                return validation_result
            
            return {
                'success': True,
                'message': f'Request validation successful for action: {action}',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error validating request: {str(e)}")
            return {
                'success': False,
                'error': f'Validation error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def _validate_specific_params(self, action: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate specific parameters for different actions.
        
        Args:
            action: The action being validated
            request_data: Request data dictionary
            
        Returns:
            Dict containing validation result
        """
        try:
            # Validate include_positions parameter
            if 'include_positions' in request_data:
                if not isinstance(request_data['include_positions'], bool):
                    # Try to convert string to boolean
                    if isinstance(request_data['include_positions'], str):
                        val = request_data['include_positions'].lower()
                        if val in ['true', '1', 'yes']:
                            request_data['include_positions'] = True
                        elif val in ['false', '0', 'no']:
                            request_data['include_positions'] = False
                        else:
                            return {
                                'success': False,
                                'error': 'include_positions must be boolean (true/false)',
                                'timestamp': datetime.now().isoformat()
                            }
            
            # Validate symbol parameter
            if 'symbol' in request_data:
                symbol = str(request_data['symbol']).strip().upper()
                if not symbol:
                    return {
                        'success': False,
                        'error': 'Symbol cannot be empty',
                        'timestamp': datetime.now().isoformat()
                    }
                # Update to uppercase
                request_data['symbol'] = symbol
            
            return {
                'success': True,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Parameter validation error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def format_request(self, json_string: str) -> Dict[str, Any]:
        """
        Parse and format a JSON string into a valid server request.
        
        Args:
            json_string: JSON string containing request data
            
        Returns:
            Dict containing formatted request or error information
        """
        try:
            # Parse JSON string
            parse_result = self.parse_json_string(json_string)
            if not parse_result['success']:
                return parse_result
            
            request_data = parse_result['data']
            
            # Validate request
            validation_result = self.validate_request(request_data)
            if not validation_result['success']:
                return validation_result
            
            # Format the request for server
            formatted_request = self._format_for_server(request_data)
            
            return {
                'success': True,
                'request': formatted_request,
                'message': f'Request formatted successfully for action: {request_data["action"]}',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting request: {str(e)}")
            return {
                'success': False,
                'error': f'Request formatting error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def _format_for_server(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format request data for server consumption.
        
        Args:
            request_data: Raw request data
            
        Returns:
            Dict formatted for server
        """
        # Create a clean copy of the request
        formatted_request = {}
        
        # Always include action (normalized to lowercase)
        formatted_request['action'] = request_data['action'].lower()
        
        # Include all other parameters, filtering out None values
        for key, value in request_data.items():
            if key != 'action' and value is not None:
                formatted_request[key] = value
        
        return formatted_request
    
    def create_request_template(self, action: str) -> Dict[str, Any]:
        """
        Create a template for a specific action with all possible parameters.
        
        Args:
            action: The action to create template for
            
        Returns:
            Dict containing request template or error
        """
        try:
            if action not in self.VALID_ACTIONS:
                return {
                    'success': False,
                    'error': f'Invalid action: {action}',
                    'valid_actions': list(self.VALID_ACTIONS)
                }
            
            template = {'action': action}
            
            # Add required parameters
            if action in self.REQUIRED_PARAMS:
                for param in self.REQUIRED_PARAMS[action]:
                    template[param] = f"<required_{param}>"
            
            # Add optional parameters
            if action in self.OPTIONAL_PARAMS:
                for param in self.OPTIONAL_PARAMS[action]:
                    template[param] = f"<optional_{param}>"
            
            return {
                'success': True,
                'template': template,
                'json_template': json.dumps(template, indent=2)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error creating template: {str(e)}'
            }
    
    def get_all_templates(self) -> Dict[str, Any]:
        """
        Get templates for all available actions.
        
        Returns:
            Dict containing all action templates
        """
        templates = {}
        
        for action in self.VALID_ACTIONS:
            template_result = self.create_request_template(action)
            if template_result['success']:
                templates[action] = template_result['template']
        
        return {
            'success': True,
            'templates': templates,
            'actions_count': len(templates)
        }
    
    def load_json_file(self, filename: str) -> Dict[str, Any]:
        """
        Load JSON content from a file.
        
        Args:
            filename: Path to the JSON file
            
        Returns:
            Dict containing loaded JSON or error information
        """
        try:
            if not filename or not filename.strip():
                return {
                    'success': False,
                    'error': 'Empty filename provided',
                    'timestamp': datetime.now().isoformat()
                }
            
            filename = filename.strip()
            
            # Check if file exists
            if not os.path.exists(filename):
                return {
                    'success': False,
                    'error': f'File not found: {filename}',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Check if it's a file (not directory)
            if not os.path.isfile(filename):
                return {
                    'success': False,
                    'error': f'Path is not a file: {filename}',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Read and parse the file
            with open(filename, 'r', encoding='utf-8') as file:
                content = file.read()
                
            if not content.strip():
                return {
                    'success': False,
                    'error': f'File is empty: {filename}',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Parse JSON content
            parse_result = self.parse_json_string(content)
            if not parse_result['success']:
                return {
                    'success': False,
                    'error': f'Invalid JSON in file {filename}: {parse_result["error"]}',
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'success': True,
                'data': parse_result['data'],
                'filename': filename,
                'timestamp': datetime.now().isoformat()
            }
            
        except PermissionError:
            return {
                'success': False,
                'error': f'Permission denied reading file: {filename}',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error loading JSON file {filename}: {str(e)}")
            return {
                'success': False,
                'error': f'Error loading file {filename}: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def combine_json_data(self, base_data: Dict[str, Any], *additional_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine multiple JSON data dictionaries, with later ones overriding earlier ones.
        
        Args:
            base_data: Base JSON data dictionary
            *additional_data: Additional dictionaries to merge
            
        Returns:
            Dict containing combined data
        """
        try:
            combined = base_data.copy()
            
            for data in additional_data:
                if isinstance(data, dict):
                    combined.update(data)
                else:
                    return {
                        'success': False,
                        'error': f'Invalid data type for combining: {type(data)}. Expected dict.',
                        'timestamp': datetime.now().isoformat()
                    }
            
            return {
                'success': True,
                'data': combined,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error combining JSON data: {str(e)}")
            return {
                'success': False,
                'error': f'Error combining JSON data: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def parse_arguments(self, *args) -> Dict[str, Any]:
        """
        Parse arguments which can be filenames or JSON strings, and combine them.
        
        Args:
            *args: Arguments that can be:
                   - Filename (string without ':' character)
                   - JSON string (string with ':' character)
                   - Dictionary
                   
        Returns:
            Dict containing parsed and combined data
        """
        try:
            if not args:
                return {
                    'success': False,
                    'error': 'No arguments provided',
                    'timestamp': datetime.now().isoformat()
                }
            
            combined_data = {}
            processed_args = []
            
            for i, arg in enumerate(args):
                if isinstance(arg, dict):
                    # Direct dictionary
                    combined_data.update(arg)
                    processed_args.append(f"arg{i+1}: dictionary")
                    
                elif isinstance(arg, str):
                    arg = arg.strip()
                    if not arg:
                        continue
                        
                    # Check if it's a filename (no ':' character) or JSON string
                    if ':' not in arg:
                        # Assume it's a filename
                        file_result = self.load_json_file(arg)
                        if not file_result['success']:
                            return file_result
                        combined_data.update(file_result['data'])
                        processed_args.append(f"arg{i+1}: file '{arg}'")
                    else:
                        # Assume it's a JSON string
                        parse_result = self.parse_json_string(arg)
                        if not parse_result['success']:
                            return {
                                'success': False,
                                'error': f'Invalid JSON in argument {i+1}: {parse_result["error"]}',
                                'timestamp': datetime.now().isoformat()
                            }
                        combined_data.update(parse_result['data'])
                        processed_args.append(f"arg{i+1}: JSON string")
                else:
                    return {
                        'success': False,
                        'error': f'Invalid argument type at position {i+1}: {type(arg)}. Expected str or dict.',
                        'timestamp': datetime.now().isoformat()
                    }
            
            if not combined_data:
                return {
                    'success': False,
                    'error': 'No valid data found in arguments',
                    'timestamp': datetime.now().isoformat()
                }
            
            return {
                'success': True,
                'data': combined_data,
                'processed_args': processed_args,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error parsing arguments: {str(e)}")
            return {
                'success': False,
                'error': f'Error parsing arguments: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def format_request_from_args(self, *args) -> Dict[str, Any]:
        """
        Parse arguments and format them into a valid server request.
        
        Args:
            *args: Arguments that can be filenames, JSON strings, or dictionaries
            
        Returns:
            Dict containing formatted request or error information
        """
        try:
            # Parse all arguments
            parse_result = self.parse_arguments(*args)
            if not parse_result['success']:
                return parse_result
            
            request_data = parse_result['data']
            
            # Validate the combined request
            validation_result = self.validate_request(request_data)
            if not validation_result['success']:
                return validation_result
            
            # Format the request for server
            formatted_request = self._format_for_server(request_data)
            
            return {
                'success': True,
                'request': formatted_request,
                'processed_args': parse_result['processed_args'],
                'message': f'Request formatted successfully for action: {request_data["action"]}',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting request from args: {str(e)}")
            return {
                'success': False,
                'error': f'Request formatting error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

# Global parser instance
json_parser = JSONRequestParser()