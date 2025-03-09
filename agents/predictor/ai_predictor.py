"""
AI Prediction Module

This module is responsible for assessing the potential market impact of detected 
blockchain events using artificial intelligence through OpenAI's API.
"""

import os
import json
import logging
import openai
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AIPredictor:
    """AI-powered predictor for market impact assessment."""
    
    def __init__(
        self,
        openai_api_key: str,
        impact_threshold: float = 0.7,  # Threshold for "significant" impact (0-1)
        historical_data_path: Optional[str] = None,  # Path to historical data
        token_metadata_path: Optional[str] = None,  # Path to token metadata
        cache_ttl: int = 3600  # Time to live for cached predictions (seconds)
    ):
        """
        Initialize the AI predictor.
        
        Args:
            openai_api_key: OpenAI API key
            impact_threshold: Threshold for "significant" impact (0-1)
            historical_data_path: Path to historical data (optional)
            token_metadata_path: Path to token metadata (optional)
            cache_ttl: Time to live for cached predictions (seconds)
        """
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.impact_threshold = impact_threshold
        self.cache_ttl = cache_ttl
        
        # Load historical data if provided
        self.historical_data = None
        if historical_data_path and os.path.exists(historical_data_path):
            try:
                self.historical_data = pd.read_csv(historical_data_path)
                logger.info(f"Loaded historical data from {historical_data_path}")
            except Exception as e:
                logger.error(f"Failed to load historical data: {e}")
        
        # Load token metadata if provided
        self.token_metadata = {}
        if token_metadata_path and os.path.exists(token_metadata_path):
            try:
                with open(token_metadata_path, 'r') as f:
                    self.token_metadata = json.load(f)
                logger.info(f"Loaded token metadata from {token_metadata_path}")
            except Exception as e:
                logger.error(f"Failed to load token metadata: {e}")
        
        # Prediction cache
        self.prediction_cache = {}
        
        logger.info("AIPredictor initialized")
    
    def predict_impact(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict the market impact of an event.
        
        Args:
            event: The event to analyze
            
        Returns:
            A dictionary with prediction results
        """
        # Check cache first
        event_id = self._get_event_id(event)
        cached_prediction = self._get_cached_prediction(event_id)
        if cached_prediction:
            logger.debug(f"Using cached prediction for event {event_id}")
            return cached_prediction
        
        # Determine prediction strategy based on event type
        event_type = event.get('type')
        if event_type == 'large_swap':
            prediction = self._predict_swap_impact(event)
        elif event_type == 'whale_movement':
            prediction = self._predict_whale_impact(event)
        elif event_type == 'trending_contract':
            prediction = self._predict_trending_contract_impact(event)
        else:
            logger.warning(f"Unknown event type: {event_type}")
            prediction = self._default_prediction(event)
        
        # Cache the prediction
        self._cache_prediction(event_id, prediction)
        
        # Determine if the impact is significant
        prediction['is_significant'] = (
            prediction.get('impact_score', 0) >= self.impact_threshold
        )
        
        return prediction
    
    def _get_event_id(self, event: Dict[str, Any]) -> str:
        """Generate a unique ID for an event."""
        # For simplicity, use event type + event-specific identifiers
        event_type = event.get('type', 'unknown')
        
        if event_type == 'large_swap':
            return f"{event_type}_{event.get('data', {}).get('transaction_hash', '')}"
        elif event_type == 'whale_movement':
            return f"{event_type}_{event.get('data', {}).get('from', '')}_{event.get('data', {}).get('to', '')}"
        elif event_type == 'trending_contract':
            return f"{event_type}_{event.get('data', {}).get('contract_address', '')}"
        else:
            # Fallback for unknown event types
            return f"{event_type}_{datetime.now().isoformat()}"
    
    def _get_cached_prediction(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a cached prediction if it exists and is not expired."""
        if event_id in self.prediction_cache:
            cached_entry = self.prediction_cache[event_id]
            if datetime.now().timestamp() - cached_entry['timestamp'] < self.cache_ttl:
                return cached_entry['prediction']
        return None
    
    def _cache_prediction(self, event_id: str, prediction: Dict[str, Any]):
        """Cache a prediction."""
        self.prediction_cache[event_id] = {
            'prediction': prediction,
            'timestamp': datetime.now().timestamp()
        }
    
    def _predict_swap_impact(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the impact of a large swap event."""
        event_data = event.get('data', {})
        token_address = event_data.get('token_address')
        token_symbol = self._get_token_symbol(token_address)
        usd_value = event_data.get('usd_value', 0)
        
        # Prepare context for the AI model
        context = self._prepare_swap_context(event_data)
        
        # Create prompt for OpenAI
        prompt = f"""
        Analyze the potential market impact of this large token swap:
        
        Token: {token_symbol if token_symbol else token_address}
        USD Value: ${usd_value:,.2f}
        
        Additional Context:
        {context}
        
        Predict:
        1. The likely short-term price impact (1-7 days)
        2. Expected trading volume increase as a percentage
        3. Probability of significant volatility increase
        4. Overall impact score (0-1)
        
        Format your response as a JSON object with the following keys:
        price_impact_percent, volume_increase_percent, volatility_probability, impact_score
        """
        
        # Get prediction from OpenAI
        response = self._get_openai_prediction(prompt)
        
        # Parse the result
        try:
            prediction = json.loads(response)
            prediction['token_address'] = token_address
            prediction['token_symbol'] = token_symbol
            prediction['event_type'] = 'large_swap'
            prediction['timestamp'] = datetime.now().isoformat()
            return prediction
        except json.JSONDecodeError:
            logger.error(f"Failed to parse OpenAI response: {response}")
            return self._default_prediction(event)
    
    def _predict_whale_impact(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the impact of a whale movement event."""
        event_data = event.get('data', {})
        token_address = event_data.get('token_address')
        token_symbol = self._get_token_symbol(token_address)
        usd_value = event_data.get('usd_value', 0)
        wallet_from = event_data.get('from')
        wallet_to = event_data.get('to')
        
        # Prepare context for the AI model
        context = self._prepare_whale_context(event_data)
        
        # Create prompt for OpenAI
        prompt = f"""
        Analyze the potential market impact of this whale wallet movement:
        
        Token: {token_symbol if token_symbol else token_address}
        USD Value: ${usd_value:,.2f}
        From: {wallet_from}
        To: {wallet_to}
        
        Additional Context:
        {context}
        
        Predict:
        1. The likely short-term price impact (1-7 days)
        2. Expected trading volume increase as a percentage
        3. Probability of significant volatility increase
        4. Overall impact score (0-1)
        
        Format your response as a JSON object with the following keys:
        price_impact_percent, volume_increase_percent, volatility_probability, impact_score
        """
        
        # Get prediction from OpenAI
        response = self._get_openai_prediction(prompt)
        
        # Parse the result
        try:
            prediction = json.loads(response)
            prediction['token_address'] = token_address
            prediction['token_symbol'] = token_symbol
            prediction['event_type'] = 'whale_movement'
            prediction['timestamp'] = datetime.now().isoformat()
            return prediction
        except json.JSONDecodeError:
            logger.error(f"Failed to parse OpenAI response: {response}")
            return self._default_prediction(event)
    
    def _predict_trending_contract_impact(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Predict the impact of a trending contract event."""
        event_data = event.get('data', {})
        contract_address = event_data.get('contract_address')
        transaction_count = event_data.get('transaction_count', 0)
        
        # Prepare context for the AI model
        context = self._prepare_trending_context(event_data)
        
        # Create prompt for OpenAI
        prompt = f"""
        Analyze the potential market impact of this trending contract:
        
        Contract Address: {contract_address}
        Transaction Count (recent): {transaction_count}
        
        Additional Context:
        {context}
        
        Predict:
        1. The likely short-term price impact on related tokens (1-7 days)
        2. Expected trading volume increase as a percentage
        3. Probability of significant volatility increase
        4. Overall impact score (0-1)
        
        Format your response as a JSON object with the following keys:
        price_impact_percent, volume_increase_percent, volatility_probability, impact_score
        """
        
        # Get prediction from OpenAI
        response = self._get_openai_prediction(prompt)
        
        # Parse the result
        try:
            prediction = json.loads(response)
            prediction['contract_address'] = contract_address
            prediction['event_type'] = 'trending_contract'
            prediction['timestamp'] = datetime.now().isoformat()
            return prediction
        except json.JSONDecodeError:
            logger.error(f"Failed to parse OpenAI response: {response}")
            return self._default_prediction(event)
    
    def _default_prediction(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a default prediction for unknown event types."""
        return {
            'price_impact_percent': 0.0,
            'volume_increase_percent': 0.0,
            'volatility_probability': 0.0,
            'impact_score': 0.0,
            'event_type': event.get('type', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'is_significant': False
        }
    
    def _prepare_swap_context(self, event_data: Dict[str, Any]) -> str:
        """Prepare context information for a swap event."""
        # In a real implementation, we would include:
        # - Historical price data for the token
        # - Recent trading volume
        # - Liquidity information
        # - Previous similar events and their outcomes
        
        # For this example, we'll return a placeholder
        return "Token is being actively traded with moderate liquidity."
    
    def _prepare_whale_context(self, event_data: Dict[str, Any]) -> str:
        """Prepare context information for a whale movement event."""
        # In a real implementation, we would include:
        # - Information about the whale wallet (past behavior)
        # - Historical price impact of similar movements
        # - Current market conditions
        
        # For this example, we'll return a placeholder
        return "Whale wallet has been active in the past month with several large transactions."
    
    def _prepare_trending_context(self, event_data: Dict[str, Any]) -> str:
        """Prepare context information for a trending contract event."""
        # In a real implementation, we would include:
        # - Contract verification status
        # - Contract interactions
        # - Similar contracts and their impact
        
        # For this example, we'll return a placeholder
        return "Contract appears to be a new DeFi protocol based on interaction patterns."
    
    def _get_token_symbol(self, token_address: str) -> Optional[str]:
        """Get token symbol from address using cached metadata."""
        if token_address in self.token_metadata:
            return self.token_metadata[token_address].get('symbol')
        return None
    
    def _get_openai_prediction(self, prompt: str) -> str:
        """Get a prediction from OpenAI API."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",  # Use appropriate model
                messages=[
                    {"role": "system", "content": "You are an AI analyzing blockchain events to predict their market impact. Return your predictions in JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Low temperature for more consistent results
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "{}"  # Return empty JSON on error


# Example usage
def example():
    """Example usage of AIPredictor."""
    # Replace with your OpenAI API key
    api_key = "sk-your-openai-api-key"
    
    predictor = AIPredictor(
        openai_api_key=api_key,
        impact_threshold=0.7
    )
    
    # Example event
    example_event = {
        'type': 'large_swap',
        'data': {
            'token_address': '0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0',  # MATIC
            'usd_value': 500000,
            'transaction_hash': '0x123abc...'
        }
    }
    
    result = predictor.predict_impact(example_event)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    # Run the example
    example() 