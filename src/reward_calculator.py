import logging
from typing import Dict, Tuple, Optional

# --- 模块级别的日志记录设置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class RewardCalculator:
    """
    A class to calculate rewards based on different strategies.
    This allows for easy swapping of reward functions in the main loop.
    """

    def calculate_reward_ener_plus_discomfort(
            self,
            kpis: Dict[str, float],
            last_objective_integrand: Optional[float]
    ) -> Tuple[float, float]:
        """
        Calculates reward based on changes in a combined objective of energy cost and thermal discomfort.

        Args:
            kpis (Dict[str, float]): A dictionary of the latest KPIs from BOPTEST.
            last_objective_integrand (Optional[float]): The objective value from the previous step.
                                                         If None (for the first step), it's initialized.

        Returns:
            Tuple[float, float]: A tuple containing the calculated reward and the new objective_integrand.
        """
        # --- 参数定义 ---
        # 权重 w, 用于平衡能耗成本和热不舒适度的重要性。
        # Weight w, to balance the importance of energy cost and thermal discomfort.
        w = 1.0

        # --- 计算逻辑 ---
        ener = kpis.get('ener_tot', 0.0)
        tdis = kpis.get('tdis_tot', 0.0)

        # 计算当前的目标函数值
        # Calculate the current objective function value
        current_objective_integrand = ener + w * tdis

        # 如果是第一步，没有上一个目标值，则奖励为0
        # If it's the first step with no previous objective, reward is 0
        if last_objective_integrand is None:
            logging.info("First reward calculation. Initializing objective, reward is 0.")
            return 0.0, current_objective_integrand

        # 奖励是目标函数值的负向变化。目标值降低意味着奖励为正。
        # Reward is the negative change in the objective function. A decrease in the objective means a positive reward.
        reward = -(current_objective_integrand - last_objective_integrand)

        logging.info(
            f"Reward calculated: {reward:.4f} (Current Objective: {current_objective_integrand:.4f}, Last Objective: {last_objective_integrand:.4f})")

        return reward, current_objective_integrand

