import random
import time

from typing import Union
from loguru import logger

from src.schemas.config import ConfigSchema
from src.bridge_manager import BridgeManager, get_all_chain_paths, get_class_object_from_main_file
from src.paths import CONTRACTS_DIR

from eth_account import Account
from eth_abi import encode
from web3 import Web3


class BridgeBase:
    def __init__(self, config: Union[ConfigSchema, None] = None):
        self.bridge_manager = BridgeManager(input_data=config)
        self.config_data = config
        self.all_chain_paths = get_all_chain_paths(CONTRACTS_DIR)
        self.source_chain = get_class_object_from_main_file(class_name=config.source_chain,
                                                            all_chain_paths=self.all_chain_paths)
        self.target_chain = get_class_object_from_main_file(class_name=config.target_chain,
                                                            all_chain_paths=self.all_chain_paths)

        self.min_bridge_amount = config.min_bridge_amount
        self.max_bridge_amount = config.max_bridge_amount

        self.web3 = self.source_chain.web3

    def get_wallet_number(self, wallet_number):
        if wallet_number is None:
            wallet_number = ""
        else:
            wallet_number = f"[{wallet_number}]"

        return wallet_number

    def get_checksum_address(self, address):
        return self.web3.to_checksum_address(address)

    def get_eth_balance(self, address):
        return self.web3.eth.get_balance(address)

    def get_token_balance(self, wallet_address, token_contract):
        balance = token_contract.functions.balanceOf(wallet_address).call()
        return balance

    def get_token_decimals(self, token_contract):
        decimals = token_contract.functions.decimals().call()
        return decimals

    def check_allowance(self, wallet_address, token_contract, spender):
        allowance = token_contract.functions.allowance(wallet_address, spender).call()
        return allowance

    def get_dst_coin_name(self, src_token_obj):
        src_token_name = src_token_obj.name
        token_objects = self.target_chain.token_contracts
        for token in token_objects:
            if token.name == src_token_name:
                return token.name

        for token in token_objects:
            return token.name

    def get_txn_fee(self, wallet_address) -> int:
        wallet_address = self.web3.to_checksum_address(wallet_address)
        fee = self.source_chain.router_contract.functions.quoteLayerZeroFee(self.target_chain.chain_id,
                                                                            1,
                                                                            wallet_address,
                                                                            "0x",
                                                                            [0, 0, wallet_address]
                                                                            ).call()
        return fee[0]

    def get_endpoint_txn_fee(self, router_address, adapter_params, chain_id):
        fee = self.source_chain.endpoint_contract.functions.estimateFees(chain_id,
                                                                         router_address,
                                                                         "0x",
                                                                         False,
                                                                         adapter_params
                                                                         ).call()
        return fee[0]

    def get_txn_fee_bridge_from_core(self, target_chain_id):
        fee = self.source_chain.router_contract.functions.estimateBridgeFee(target_chain_id,
                                                                            False,
                                                                            "0x",
                                                                            ).call()
        return fee[0]

    def get_core_bridge_fee(self, adapter_params):
        fee = self.source_chain.core_dao_router_contract.functions.estimateBridgeFee(False,
                                                                                     adapter_params
                                                                                     ).call()
        return fee[0]

    def get_estimate_gas(self, transaction):
        estimated_gas_limit = self.source_chain.web3.eth.estimate_gas(transaction)
        return estimated_gas_limit

    def get_wallet_nonce(self, wallet_address):
        return self.web3.eth.get_transaction_count(wallet_address)

    def get_wallet_address(self, private_key):
        account = Account.from_key(private_key)
        return self.web3.to_checksum_address(account.address)

    def get_amount_out_min(self, amount_out):
        return int(amount_out - (amount_out * self.config_data.slippage // 100))

    def get_gas_price(self):
        if self.config_data.custom_gas_price is True:
            if self.config_data.gas_price is not None:
                return self.web3.to_wei(self.config_data.gas_price, 'gwei')
            else:
                return self.web3.eth.gas_price
        else:
            if self.config_data.source_chain.lower() == 'arbitrum':
                return int(self.web3.eth.gas_price * 1.35)
            elif self.config_data.source_chain.lower() == 'polygon':
                return int(self.web3.eth.gas_price * 1.35)
            elif self.config_data.source_chain.lower() == 'avalanche':
                return int(self.web3.eth.gas_price * 1.15)
            else:
                return self.web3.eth.gas_price

    def get_pool_id(self, token_obj):
        try:
            token_obj_pool_id = token_obj.pool_id
        except Exception as e:
            token_obj_pool_id = None

        return token_obj_pool_id

    def allowance_check_loop(self, wallet_address, target_allowance_amount, token_contract, spender):
        process_start_time = time.time()
        while True:
            if time.time() - process_start_time > 150:
                return False

            current_allowance = self.check_allowance(wallet_address=wallet_address,
                                                     token_contract=token_contract,
                                                     spender=spender)
            logger.debug(f"Waiting allowance txn, allowance: {current_allowance}, need: {target_allowance_amount}, "
                         f"time passed: {time.time() - process_start_time}")

            if current_allowance >= target_allowance_amount:
                return True
            time.sleep(3)

    def make_approve_for_token(self, private_key, target_approve_amount, token_contract, token_obj, spender):
        wallet_address = self.get_wallet_address(private_key)
        approve_amount = int((10 ** 8) * 10 ** self.get_token_decimals(token_contract))
        allowance_txn = self.build_allowance_tx(wallet_address=wallet_address,
                                                token_contract=token_contract,
                                                amount_out=approve_amount,
                                                spender=spender)
        try:
            estimate_gas_limit = self.get_estimate_gas(allowance_txn)

            if estimate_gas_limit < self.config_data.gas_limit:
                allowance_txn['gas'] = estimate_gas_limit

            if self.config_data.test_mode is True:
                logger.info(f"[{wallet_address}] - Estimated gas limit for {token_obj.name}"
                            f" approve: {estimate_gas_limit}. You are currently in test mode")
                return

            signed_txn = self.web3.eth.account.sign_transaction(allowance_txn, private_key=private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.success(f"[{wallet_address}] - Approve transaction sent: {tx_hash.hex()}")
            time.sleep(0.2)

            allowance_check = self.allowance_check_loop(wallet_address=wallet_address,
                                                        target_allowance_amount=target_approve_amount,
                                                        token_contract=token_contract,
                                                        spender=spender)
            if allowance_check is True:
                logger.info(f"[{wallet_address}] - Approve transaction confirmed")
                time.sleep(2)
                return True
            else:
                logger.info(f"[{wallet_address}] - Allowance process took more than 150 seconds, aborting")
                return False

        except Exception as e:
            logger.error(f"[{wallet_address}] - Error while approving txn: {e}")
            return False

    def get_random_amount_out(self, min_amount, max_amount, token_contract=None):
        random_amount = random.uniform(min_amount, max_amount)

        if token_contract is None:
            token_amount_out = Web3.to_wei(random_amount, 'ether')
        else:
            token_amount_out = int(round(random_amount, 3) * 10 ** self.get_token_decimals(token_contract))

        return token_amount_out

    def gef_get_adapter_params(self, recipient_address: bytes):
        encoded_params = encode(["uint16", "uint256", "uint", "bytes32"],
                                [2, 10000, 0, recipient_address]).hex()
        params = '000' + encoded_params.lstrip('0')
        params_bytes = bytes.fromhex(params)
        return params_bytes

    def get_adapter_params_v1(self, gas_on_destination: int):
        encoded_params = encode(["uint16", "uint256"],
                                [1, int(gas_on_destination)]).hex()
        params = '000' + encoded_params.lstrip('0')
        params_bytes = bytes.fromhex(params)
        return params_bytes

    def build_allowance_tx(self, wallet_address, token_contract, amount_out, spender):
        nonce = self.get_wallet_nonce(wallet_address=wallet_address)
        gas_price = self.get_gas_price()
        gas_limit = self.config_data.gas_limit
        allowance_transaction = token_contract.functions.approve(
            spender,
            int(amount_out)
        ).build_transaction({
            'from': wallet_address,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
        })
        return allowance_transaction

    def build_eth_bridge_tx(self, wallet_address, amount_out, chain_id, dst_wallet_address):
        fee: int = self.get_txn_fee(wallet_address=wallet_address)
        amount_out_min = self.get_amount_out_min(amount_out=amount_out)
        nonce = self.get_wallet_nonce(wallet_address=wallet_address)
        gas_price = self.get_gas_price()
        gas_limit = self.config_data.gas_limit
        bridge_transaction = self.source_chain.eth_router_contract.functions.swapETH(
            chain_id,
            wallet_address,
            dst_wallet_address,
            amount_out,
            amount_out_min
        ).build_transaction({
            'from': wallet_address,
            'value': amount_out + fee,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
        })

        return bridge_transaction

    def build_token_bridge_tx(self, wallet_address, amount_out, chain_id, src_token_obj, dst_token_obj,
                              dst_wallet_address):

        fee: int = self.get_txn_fee(wallet_address=wallet_address)
        amount_out_min = self.get_amount_out_min(amount_out=amount_out)
        nonce = self.get_wallet_nonce(wallet_address=wallet_address)
        gas_price = self.get_gas_price()
        gas_limit = self.config_data.gas_limit

        src_pool_id = self.get_pool_id(token_obj=src_token_obj)
        dst_pool_id = self.get_pool_id(token_obj=dst_token_obj)
        if src_pool_id is None or dst_pool_id is None:
            return None

        bridge_transaction = self.source_chain.router_contract.functions.swap(
            chain_id,
            src_pool_id,
            dst_pool_id,
            wallet_address,
            amount_out,
            amount_out_min,
            [0, 0, '0x0000000000000000000000000000000000000001'],
            dst_wallet_address,
            "0x"
        ).build_transaction({
            'from': wallet_address,
            'value': fee,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
        })

        return bridge_transaction

    def build_token_bridge_to_aptos_tx(self, source_wallet_address, recipient_address: bytes, amount_out, token_obj):
        zro_payment_address = self.web3.to_checksum_address('0x0000000000000000000000000000000000000000')
        adapter_params = self.gef_get_adapter_params(recipient_address=recipient_address)
        fee: int = self.get_endpoint_txn_fee(chain_id=108,
                                             router_address=self.source_chain.aptos_router_address,
                                             adapter_params=adapter_params)
        gas_price = self.get_gas_price()
        gas_limit = self.config_data.gas_limit
        bridge_transaction = self.source_chain.aptos_router_contract.functions.sendToAptos(
            token_obj.address,
            recipient_address,
            amount_out,
            [source_wallet_address, zro_payment_address],
            adapter_params
        ).build_transaction({
            'from': source_wallet_address,
            'value': int(fee * 1.1),
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': self.get_wallet_nonce(wallet_address=source_wallet_address),
        })

        return bridge_transaction

    def build_eth_bridge_to_aptos_tx(self, source_wallet_address, recipient_address: bytes, amount_out):
        zro_payment_address = self.web3.to_checksum_address('0x0000000000000000000000000000000000000000')
        adapter_params = self.gef_get_adapter_params(recipient_address=recipient_address)
        fee: int = self.get_endpoint_txn_fee(chain_id=108,
                                             router_address=self.source_chain.aptos_router_address,
                                             adapter_params=adapter_params)
        bridge_transaction = self.source_chain.aptos_router_contract.functions.sendETHToAptos(
            recipient_address,
            amount_out,
            [source_wallet_address, zro_payment_address],
            adapter_params
        ).build_transaction({
            'from': source_wallet_address,
            'value': int(fee * 1.1 + amount_out),
            'gas': self.config_data.gas_limit,
            'gasPrice': self.get_gas_price(),
            'nonce': self.get_wallet_nonce(wallet_address=source_wallet_address),
        })
        return bridge_transaction

    def build_token_bridge_core_tx(self, wallet_address, amount_out, token_obj, dst_wallet_address):
        zro_payment_address = self.web3.to_checksum_address('0x0000000000000000000000000000000000000000')
        fee: int = self.get_core_bridge_fee(adapter_params='0x')
        bridge_transaction = self.source_chain.core_dao_router_contract.functions.bridge(
            token_obj.address,
            amount_out,
            dst_wallet_address,
            [wallet_address, zro_payment_address],
            '0x'
        ).build_transaction({
            'from': wallet_address,
            'value': fee,
            'gas': self.config_data.gas_limit,
            'gasPrice': self.get_gas_price(),
            'nonce': self.get_wallet_nonce(wallet_address=wallet_address)
        })
        return bridge_transaction

    def build_token_bridge_frome_core_tx(self, wallet_address, amount_out, token_obj, dst_wallet_address):
        zro_payment_address = self.web3.to_checksum_address('0x0000000000000000000000000000000000000000')
        fee: int = self.get_txn_fee_bridge_from_core(target_chain_id=self.target_chain.chain_id)

        bridge_transaction = self.source_chain.router_contract.functions.bridge(
            token_obj.address,
            self.target_chain.chain_id,
            amount_out,
            dst_wallet_address,
            True,
            [wallet_address, zro_payment_address],
            '0x'
        ).build_transaction({
            'from': wallet_address,
            'value': fee,
            'gas': self.config_data.gas_limit,
            'gasPrice': self.get_gas_price(),
            'nonce': self.get_wallet_nonce(wallet_address=wallet_address)
        })
        return bridge_transaction

    def build_stg_bridge_txn(self, src_wallet_address, dst_wallet_address, amount_out, token_obj, dst_cain_id):
        zro_payment_address = self.web3.to_checksum_address('0x0000000000000000000000000000000000000000')
        fee: int = self.get_txn_fee(wallet_address=src_wallet_address)
        adapter_params = self.get_adapter_params_v1(gas_on_destination=85000)
        token_contract = self.web3.eth.contract(address=token_obj.address, abi=token_obj.abi)

        bridge_transaction = token_contract.functions.sendTokens(
            dst_cain_id,
            dst_wallet_address,
            amount_out,
            zro_payment_address,
            adapter_params
        ).build_transaction({
            'from': src_wallet_address,
            'gas': self.config_data.gas_limit,
            'value': fee,
            'gasPrice': self.get_gas_price(),
            'nonce': self.get_wallet_nonce(wallet_address=src_wallet_address)
        })
        return bridge_transaction



