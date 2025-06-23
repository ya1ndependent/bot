def quotation_to_float(q):
    return q.units + q.nano / 1e9
    
# Список самых ликвидных/волатильных тикеров МосБиржи:
TICKERS = ["SBER", "GAZP", "LKOH", "YNDX", "MGNT"]

# Соответствующие FIGI (можно уточнить в API или на сайте):
FIGI_MAP = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG0047YPYT6",
    "LKOH": "BBG004730F41",
    "YNDX": "BBG006L8G4H1",
    "MGNT": "BBG004730Z98",
}
