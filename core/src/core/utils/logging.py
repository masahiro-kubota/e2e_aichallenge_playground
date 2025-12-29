import logging

# グローバルなシミュレーション時刻
_current_sim_time = 0.0


def set_sim_time(t: float) -> None:
    """グローバルなシミュレーション時刻を更新します。"""
    global _current_sim_time
    _current_sim_time = t


class SimTimeFilter(logging.Filter):
    """ログレコードにシミュレーション時刻と短縮ノード名を付与するフィルター。"""

    def filter(self, record: logging.LogRecord) -> bool:
        # シミュレーション時刻をセット (小数点3桁)
        record.sim_time = f"{_current_sim_time:.3f}s"

        # 名前が長い場合に短縮 (末尾の部分のみ使用)
        # 例: ad_components.control.pure_pursuit_controller -> pure_pursuit_controller
        if "." in record.name:
            record.short_name = record.name.split(".")[-1]
        else:
            record.short_name = record.name

        return True
