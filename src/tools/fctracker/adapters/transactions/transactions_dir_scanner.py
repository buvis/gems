from fctracker.adapters.config.config import cfg


class TransactionsDirScanner:
    def __init__(self) -> None:
        self._dir_path = cfg.transactions_dir
        self.accounts: dict[str, list[str]] = {}

        for account_dir in self._dir_path.iterdir():
            account_name = f"{account_dir.name}".capitalize()
            self.accounts[account_name] = []

            for item in account_dir.iterdir():
                if item.is_file() is True:
                    if item.suffix == ".csv":
                        self.accounts[account_name].append(item.stem.upper())
