from src.config import get_add_liquidity_config
from src.stake_manager import LiquidityManager

from stake.add_liquidity.main import mass_add_liquidity


def run_config():
    config = get_add_liquidity_config()
    stake_manager = LiquidityManager(input_data=config)
    error_msg = stake_manager.check_if_route_eligible()

    if error_msg is not True:
        print(error_msg)
        return

    mass_add_liquidity(config=config)


if __name__ == '__main__':
    run_config()