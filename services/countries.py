COUNTRIES = [
    ("Brasil", "português do Brasil", "R$"),
    ("Portugal", "português de Portugal", "€"),
    ("Estados Unidos", "English (US)", "$"),
    ("Reino Unido", "English (UK)", "£"),
    ("Canadá", "English (Canada)", "CA$"),
    ("México", "español de México", "$"),
    ("Espanha", "español de España", "€"),
    ("Argentina", "español de Argentina", "$"),
    ("França", "français", "€"),
    ("Alemanha", "Deutsch", "€"),
    ("Itália", "italiano", "€"),
]

COUNTRY_NAMES = [item[0] for item in COUNTRIES]


def country_info(name):
    for item in COUNTRIES:
        if item[0] == name:
            return item
    return COUNTRIES[0]
