import time
import random

from datetime import datetime, timedelta

from bridge_swap.base_bridge import BridgeBase
from src.files_manager import read_evm_wallets_from_file, read_aptos_wallets_from_file
from src.schemas.config import ConfigSchema
from src.config import get_config, print_config
from src.rpc_manager import RpcValidator

from loguru import logger


def eth_mass_transfer_to_aptos(config_data: ConfigSchema):
    print_config(config=config_data)

    token_bridge = EthBridgeManualAptos(config=config_data)

    evm_wallets: list = read_evm_wallets_from_file()
    aptos_wallets: list = read_aptos_wallets_from_file()

    if config_data.send_to_one_address is True:
        wallets_amount = len(evm_wallets)
        aptos_wallet = config_data.address_to_send

        for wallet in range(wallets_amount):
            bridge_status = token_bridge.eth_transfer(private_key=evm_wallets[wallet],
                                                      aptos_wallet_address=aptos_wallet,
                                                      wallet_number=wallet + 1)

            if wallet == wallets_amount - 1:
                logger.info(f"Bridge process is finished\n")
                break

            if bridge_status is not None:
                time_delay = random.randint(config_data.min_delay_seconds, config_data.max_delay_seconds)
            else:
                time_delay = 3

            if time_delay == 0:
                time.sleep(0.3)
                continue

            delta = timedelta(seconds=time_delay)
            result_datetime = datetime.now() + delta

            logger.info(f"Waiting {time_delay} seconds, next wallet bridge {result_datetime}\n")
            time.sleep(time_delay)

    else:
        wallets_amount = min(len(evm_wallets), len(aptos_wallets))
        for wallet in range(wallets_amount):
            bridge_status = token_bridge.eth_transfer(private_key=evm_wallets[wallet],
                                                      aptos_wallet_address=aptos_wallets[wallet],
                                                      wallet_number=wallet + 1)

            if wallet == wallets_amount - 1:
                logger.info(f"Bridge process is finished\n")
                break

            if bridge_status is not None:
                time_delay = random.randint(config_data.min_delay_seconds, config_data.max_delay_seconds)
            else:
                time_delay = 3

            if time_delay == 0:
                time.sleep(0.3)
                continue

            delta = timedelta(seconds=time_delay)
            result_datetime = datetime.now() + delta

            logger.info(f"Waiting {time_delay} seconds, next wallet bridge {result_datetime}\n")
            time.sleep(time_delay)


def token_mass_transfer_to_aptos(config_data: ConfigSchema):
    print_config(config=config_data)

    rpc_validator = RpcValidator()
    rpcs = rpc_validator.validated_rpcs

    evm_wallets: list = read_evm_wallets_from_file()
    aptos_wallets: list = read_aptos_wallets_from_file()

    token_bridge = TokenBridgeManualAptos(config=config_data)

    if config_data.send_to_one_address is True:
        wallets_amount = len(evm_wallets)
        aptos_wallet = config_data.address_to_send

        for wallet in range(wallets_amount):
            bridge_status = token_bridge.token_transfer(private_key=evm_wallets[wallet],
                                                        aptos_wallet_address=aptos_wallet,
                                                        wallet_number=wallet + 1)

            if wallet == wallets_amount - 1:
                logger.info(f"Bridge process is finished\n")
                break

            if bridge_status is not None:
                time_delay = random.randint(config_data.min_delay_seconds, config_data.max_delay_seconds)
            else:
                time_delay = 3

            if time_delay == 0:
                time.sleep(0.3)
                continue

            delta = timedelta(seconds=time_delay)
            result_datetime = datetime.now() + delta

            logger.info(f"Waiting {time_delay} seconds, next wallet bridge {result_datetime}\n")
            time.sleep(time_delay)
    else:
        wallets_amount = min(len(evm_wallets), len(aptos_wallets))
        for wallet in range(wallets_amount):
            bridge_status = token_bridge.token_transfer(private_key=evm_wallets[wallet],
                                                        aptos_wallet_address=aptos_wallets[wallet],
                                                        wallet_number=wallet + 1)

            if wallet == wallets_amount - 1:
                logger.info(f"Bridge process is finished\n")
                break

            if bridge_status is not None:
                time_delay = random.randint(config_data.min_delay_seconds, config_data.max_delay_seconds)
            else:
                time_delay = 3

            if time_delay == 0:
                time.sleep(0.3)
                continue


            delta = timedelta(seconds=time_delay)
            result_datetime = datetime.now() + delta

            logger.info(f"Waiting {time_delay} seconds, next wallet bridge {result_datetime}\n")
            time.sleep(time_delay)


def token_mass_approve_to_aptos(config_data: ConfigSchema):
    print_config(config=config_data)

    wallets = read_evm_wallets_from_file()
    token_bridge = TokenBridgeManualAptos(config=config_data)
    wallet_number = 1

    time_start = time.time()
    for wallet in wallets:
        token_bridge.approve_token_transfer(private_key=wallet, wallet_number=wallet_number)
        wallet_number += 1
    time_end = time.time() - time_start

    if time_end < 30:
        logger.warning(f"Approve process took less than 30 sec. Waiting 20 sec to start bridge process")
        time.sleep(20)


class EthBridgeManualAptos(BridgeBase):
    def __init__(self, config: ConfigSchema):
        super().__init__(config=config)

    def eth_transfer(self, private_key, wallet_number, aptos_wallet_address=None):
        source_wallet_address = self.get_wallet_address(private_key=private_key)
        wallet_eth_balance_wei = self.get_eth_balance(address=source_wallet_address)
        wallet_eth_balance = self.web3.from_wei(wallet_eth_balance_wei, 'ether')

        if self.config_data.send_to_one_address is True:
            dst_wallet_address = self.web3.to_bytes(hexstr=self.config_data.address_to_send)
        else:
            dst_wallet_address = self.web3.to_bytes(hexstr=aptos_wallet_address)
            if dst_wallet_address is None:
                logger.error(f"[{wallet_number}] [{source_wallet_address}] - No aptos address provided")
                return

        eth_amount_out = self.get_random_amount_out(min_amount=self.min_bridge_amount,
                                                    max_amount=self.max_bridge_amount)

        if wallet_eth_balance_wei < eth_amount_out:
            logger.info(f"[{wallet_number}] [{source_wallet_address}] - Not enough eth balance ({wallet_eth_balance})"
                        f" for bridge")
            return

        txn = self.build_eth_bridge_to_aptos_tx(source_wallet_address=source_wallet_address,
                                                recipient_address=dst_wallet_address,
                                                amount_out=eth_amount_out)

        try:
            estimated_gas_limit = self.get_estimate_gas(transaction=txn)

            if self.config_data.gas_limit > estimated_gas_limit:
                txn['gas'] = int(estimated_gas_limit + (estimated_gas_limit * 0.6))

            if self.config_data.test_mode is True:
                logger.info(f"[{source_wallet_address}] - Estimated gas limit for ETH"
                            f" bridge: {estimated_gas_limit}")
                return

            signed_txn = self.web3.eth.account.sign_transaction(txn, private_key=private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.success(f"[{wallet_number}] [{source_wallet_address}] - Bridge transaction sent: {tx_hash.hex()}")

            return tx_hash.hex()

        except Exception as e:
            logger.error(f"[{wallet_number}] [{source_wallet_address}] - Error while sending bridge transaction: {e}")
            return False


class TokenBridgeManualAptos(BridgeBase):
    def __init__(self, config: ConfigSchema):
        super().__init__(config=config)
        try:
            self.token_obj = self.bridge_manager.detect_coin(coin_query=config.coin_to_transfer,
                                                             chain_query=self.config_data.source_chain)
            self.token_contract = self.web3.eth.contract(address=self.token_obj.address,
                                                         abi=self.token_obj.abi)

        except AttributeError:
            logger.error(f"Bridge of {self.config_data.coin_to_transfer} is not supported between"
                         f" {self.config_data.source_chain} and {self.config_data.target_chain}")

    def allowance_check_loop(self, private_key, target_allowance_amount):
        wallet_address = self.get_wallet_address(private_key=private_key)
        start_time = time.time()
        while True:
            if time.time() - start_time > 180:
                return False

            allowance_amount = self.check_allowance(wallet_address=wallet_address,
                                                    token_contract=self.token_contract,
                                                    spender=self.source_chain.aptos_router_address)
            logger.debug(f"Waiting allowance txn, allowance: {allowance_amount}, need: {target_allowance_amount}")
            if allowance_amount >= target_allowance_amount:
                return True
            time.sleep(2)

    def approve_token_transfer(self, private_key, approve_amount, wallet_number=None):
        wallet_address = self.get_wallet_address(private_key=private_key)
        amount_to_approve = int(1000000000 * 10 ** self.get_token_decimals(self.token_contract))
        allowance_txn = self.build_allowance_tx(wallet_address=wallet_address,
                                                token_contract=self.token_contract,
                                                amount_out=amount_to_approve,
                                                spender=self.source_chain.aptos_router_address)

        try:
            estimated_gas_limit = self.get_estimate_gas(transaction=allowance_txn)

            if self.config_data.gas_limit > estimated_gas_limit:
                allowance_txn['gas'] = estimated_gas_limit

            if self.config_data.test_mode is True:
                logger.info(f"[{wallet_address}] - Estimated gas limit for {self.token_obj.name}"
                            f" approve: {estimated_gas_limit}")
                return

            if wallet_number is None:
                wallet_number = ""
            else:
                wallet_number = f"{wallet_number}"

            signed_txn = self.web3.eth.account.sign_transaction(allowance_txn, private_key=private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.success(f"{wallet_number} [{wallet_address}] - Approve transaction sent: {tx_hash.hex()}")
            time.sleep(0.2)

            allowance_check_loop = self.allowance_check_loop(private_key=private_key,
                                                             target_allowance_amount=approve_amount)

            if allowance_check_loop is True:
                logger.info(f"{wallet_number} [{wallet_address}] - Approve transaction confirmed")
                time.sleep(2)
                return True
            else:
                logger.error(
                    f"{wallet_number} [{wallet_address}] - Approve transaction took too long, aborting transfer")
                return False

        except Exception as e:
            logger.error(f"[{wallet_number}] [{wallet_address}] - Error while sending approval transaction: {e}")
            return False

    def token_transfer(self, private_key, wallet_number, aptos_wallet_address=None):
        if not self.token_obj:
            return

        source_wallet_address = self.get_wallet_address(private_key=private_key)
        wallet_token_balance_wei = self.get_token_balance(wallet_address=source_wallet_address,
                                                          token_contract=self.token_contract)
        wallet_token_balance = wallet_token_balance_wei / 10 ** self.get_token_decimals(self.token_contract)

        if wallet_number is None:
            wallet_number = ""
        else:
            wallet_number = f"[{wallet_number}]"

        if self.config_data.send_to_one_address is True:
            dst_wallet_address = self.web3.to_bytes(hexstr=self.config_data.address_to_send)
        else:
            dst_wallet_address = dst_wallet_address = self.web3.to_bytes(hexstr=aptos_wallet_address)
            if dst_wallet_address is None:
                logger.error(f"[{wallet_number}] [{source_wallet_address}] - No aptos address provided")
                return

        if self.config_data.send_all_balance is True:
            token_amount_out = wallet_token_balance_wei
            if token_amount_out == 0:
                logger.error(f"{wallet_number} [{source_wallet_address}] - {self.config_data.coin_to_transfer} "
                             f"({self.config_data.source_chain}) balance is 0")
                return
        else:
            token_amount_out = self.get_random_amount_out(min_amount=self.min_bridge_amount,
                                                          max_amount=self.max_bridge_amount,
                                                          token_contract=self.token_contract)

        if wallet_token_balance_wei < token_amount_out:
            logger.error(f"[{wallet_number}] [{source_wallet_address}] - {self.config_data.coin_to_transfer} "
                         f"({self.config_data.source_chain}) balance not enough "
                         f"to bridge. Balance: {wallet_token_balance}")
            return

        allowed_amount_to_bridge = self.check_allowance(wallet_address=source_wallet_address,
                                                        token_contract=self.token_contract,
                                                        spender=self.source_chain.aptos_router_address)

        if allowed_amount_to_bridge < token_amount_out:
            logger.warning(
                f"{wallet_number} [{source_wallet_address}] - Not enough allowance for {self.token_obj.name},"
                f" approving {self.token_obj.name} to bridge")
            approve_amount = int(1000000000 * 10 ** self.get_token_decimals(self.token_contract))
            approve_txn = self.approve_token_transfer(private_key=private_key,
                                                      wallet_number=wallet_number,
                                                      approve_amount=approve_amount)
            if approve_txn is not True:
                return
        else:
            logger.info(f"[{wallet_number}] [{source_wallet_address}] - Wallet has enough allowance to bridge")

        txn = self.build_token_bridge_to_aptos_tx(amount_out=token_amount_out,
                                                  token_obj=self.token_obj,
                                                  recipient_address=dst_wallet_address,
                                                  source_wallet_address=source_wallet_address)
        try:
            estimated_gas_limit = self.get_estimate_gas(transaction=txn)

            if self.config_data.gas_limit > estimated_gas_limit:
                txn['gas'] = estimated_gas_limit

            if self.config_data.test_mode is True:
                logger.info(
                    f"[{wallet_number}] [{source_wallet_address}] - Estimated gas limit for {self.config_data.source_chain}"
                    f" → Aptos "
                    f"{self.token_obj.name} bridge: {estimated_gas_limit}")
                return

            signed_txn = self.web3.eth.account.sign_transaction(txn, private_key=private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.success(f"[{wallet_number}] [{source_wallet_address}] - Transaction sent: {tx_hash.hex()}")

            return tx_hash.hex()

        except Exception as e:
            logger.error(
                f"[{wallet_number}] [{source_wallet_address}] - Error while sending  transaction: {e}")
            return


if __name__ == '__main__':
    config = get_config()
    eth_mass_transfer_to_aptos(config_data=config)
