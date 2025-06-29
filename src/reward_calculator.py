import logging
from typing import Dict, Tuple, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class RewardCalculator:
    """
    一个包含多种奖励计算策略的工具箱。
    A toolbox containing various reward calculation strategies.
    """

    def calculate_reward_ener_plus_discomfort(
            self,
            kpis: Dict[str, float],
            last_objective_integrand: Optional[float]
    ) -> Tuple[float, float]:
        """
        策略1: 平衡能耗与不舒适度。
        Strategy 1: Balance energy consumption and discomfort.
        """
        w = 1.0  # 平衡权重 (Balancing weight)
        ener = kpis.get('ener_tot', 0.0)
        tdis = kpis.get('tdis_tot', 0.0)

        current_objective_integrand = ener + w * tdis

        if last_objective_integrand is None:
            return 0.0, current_objective_integrand

        reward = -(current_objective_integrand - last_objective_integrand)
        logging.info(f"Reward (Energy+Discomfort): {reward:.4f}")
        return reward, current_objective_integrand

    def calculate_reward_comfort_focus(
            self,
            kpis: Dict[str, float],
            last_objective_integrand: Optional[float]
    ) -> Tuple[float, float]:
        """
        【新增】策略2: 优先保证舒适度。
        [NEW] Strategy 2: Prioritize thermal comfort.
        """
        # 在这个策略中，我们给不舒适度一个非常高的权重，是能耗的10倍。
        # In this strategy, we give discomfort a much higher weight, 10x that of energy.
        w_comfort = 10.0
        w_energy = 1.0

        ener = kpis.get('ener_tot', 0.0)
        tdis = kpis.get('tdis_tot', 0.0)

        current_objective_integrand = (w_energy * ener) + (w_comfort * tdis)

        if last_objective_integrand is None:
            return 0.0, current_objective_integrand

        reward = -(current_objective_integrand - last_objective_integrand)
        logging.info(f"Reward (Comfort Focus): {reward:.4f}")
        return reward, current_objective_integrand

