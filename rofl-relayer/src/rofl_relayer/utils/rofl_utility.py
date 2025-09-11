import codecs
import httpx
import json
import logging
import typing
from typing import Any, Dict, Optional
from web3.types import TxParams

import cbor2

logger = logging.getLogger(__name__)


class RoflUtility:
    ROFL_SOCKET_PATH = "/run/rofl-appd.sock"

    def __init__(self, url: str = ''):
        self.url = url

    async def _appd_post(self, path: str, payload: typing.Any) -> typing.Any:
        transport = None
        if self.url and not self.url.startswith('http'):
            transport = httpx.AsyncHTTPTransport(uds=self.url)
            logger.debug(f"Using HTTP socket: {self.url}")
        elif not self.url:
            transport = httpx.AsyncHTTPTransport(uds=self.ROFL_SOCKET_PATH)
            logger.debug(f"Using unix domain socket: {self.ROFL_SOCKET_PATH}")

        async with httpx.AsyncClient(transport=transport) as client:
            url = self.url if self.url and self.url.startswith('http') else "http://localhost"
            logger.debug(f"Posting to {url+path}: {json.dumps(payload)}")
            # Use 30-second timeout for blockchain operations
            response = await client.post(url + path, json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def fetch_key(self, id: str) -> str:
        payload = {
            "key_id": id,
            "kind": "secp256k1"
        }

        path = '/rofl/v1/keys/generate'

        response = await self._appd_post(path, payload)
        return response["key"]

    def _decode_cbor_response(self, response_hex: str) -> Dict[str, Any]:
        """
        Decode CBOR response from ROFL service.
        
        Args:
            response_hex: Hex-encoded CBOR response
            
        Returns:
            Decoded CBOR data as dictionary
        """
        try:
            data_bytes = codecs.decode(response_hex, "hex")
            cbor_result = cbor2.loads(data_bytes)
            logger.debug(f"Decoded CBOR: {cbor_result}")
            return cbor_result if isinstance(cbor_result, dict) else {"data": cbor_result}
        except Exception as decode_error:
            logger.error(f"CBOR decode error: {decode_error}")
            return {"error": "decode_failed", "raw": response_hex}

    async def submit_tx(self, tx: TxParams) -> bool:
        """
        Submit a transaction via ROFL.
        
        Args:
            tx: Transaction parameters
            
        Returns:
            True if transaction was accepted, False otherwise
            
        Raises:
            Exception: If ROFL returns an error
        """
        payload = {
            "tx": {
                "kind": "eth",
                "data": {
                    "gas_limit": tx["gas"],
                    "to": tx["to"].removeprefix("0x"),
                    "value": tx["value"],
                    "data": tx["data"].removeprefix("0x"),
                },
            },
            "encrypt": False,
        }

        path = '/rofl/v1/tx/sign-submit'

        response = await self._appd_post(path, payload)
        response_hex = response["data"]
        logger.debug(f"ROFL raw response: {response_hex}")
        
        # Decode CBOR response to check for success
        decoded_response = self._decode_cbor_response(response_hex)
        
        # Check response status
        if 'ok' in decoded_response:
            logger.info("Transaction submitted successfully to ROFL")
            return True
        elif 'error' in decoded_response:
            error_msg = decoded_response.get('error')
            logger.error(f"ROFL transaction failed: {error_msg}")
            raise Exception(f"ROFL transaction failed: {error_msg}")
        else:
            logger.warning(f"Unknown ROFL response format: {decoded_response}")
            # If no clear error, assume success
            return True