"""Round-trip tests for congressional trade types, including option metadata."""

from sentisense import AssetMetadata, CongressTrade


class TestCongressTrade:
    def test_plain_stock_has_no_asset_metadata(self):
        trade = CongressTrade.from_dict({
            "politicianName": "Nancy Pelosi",
            "ticker": "NVDA",
            "assetType": "Stock",
            "transactionType": "PURCHASE",
            "transactionDate": "2026-03-15",
        })
        assert trade.ticker == "NVDA"
        assert trade.assetType == "Stock"
        assert trade.assetMetadata is None

    def test_option_trade_parses_nested_metadata(self):
        trade = CongressTrade.from_dict({
            "politicianName": "Nancy Pelosi",
            "ticker": "NVDA",
            "assetType": "Stock Option",
            "assetMetadata": {
                "kind": "OPTION",
                "optionType": "CALL",
                "strikePrice": 50,
                "expirationDate": "2026-12-18",
            },
            "transactionType": "PURCHASE",
        })
        assert trade.assetType == "Stock Option"
        assert isinstance(trade.assetMetadata, AssetMetadata)
        assert trade.assetMetadata.kind == "OPTION"
        assert trade.assetMetadata.optionType == "CALL"
        assert trade.assetMetadata.strikePrice == 50
        assert trade.assetMetadata.expirationDate == "2026-12-18"

    def test_null_asset_metadata_stays_none(self):
        trade = CongressTrade.from_dict({
            "ticker": "AAPL",
            "assetType": "ETF",
            "assetMetadata": None,
        })
        assert trade.assetMetadata is None

    def test_unknown_keys_ignored(self):
        trade = CongressTrade.from_dict({
            "ticker": "AAPL",
            "someFutureField": "ignored",
        })
        assert trade.ticker == "AAPL"
        assert not hasattr(trade, "someFutureField")
