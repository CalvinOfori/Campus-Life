"""Campus shop catalog mapped to the local product photos in assets/."""

PRODUCTS = [
    {
        "id": "campus-notebook", "name": "Campus notebook", "category": "Stationery",
        "price": "0.0048", "image": "notebook.jpg", "popular": True,
        "description": "A colorful spiral notebook for lecture notes, plans, and new ideas between classes.",
        "rating": "4.8", "reviews": 128,
    },
    {
        "id": "snack-bar", "name": "Chocolate snack bar", "category": "Snacks",
        "price": "0.0018", "image": "snackbar.jpg", "popular": True,
        "description": "A quick chocolate break for long lectures and late study sessions.",
        "rating": "4.7", "reviews": 94,
    },
    {
        "id": "phone-charger", "name": "USB-C phone charger cable", "category": "Electronics",
        "price": "0.0065", "image": "phone-charger.jpg", "popular": True,
        "description": "A durable braided cable to keep your phone charged through the campus day.",
        "rating": "4.6", "reviews": 76,
    },
    {
        "id": "print-credit", "name": "Printer paper pack", "category": "Printing",
        "price": "0.003", "image": "print.jpg", "popular": True,
        "description": "A handy paper pack for lecture slides, project drafts, and final submissions.",
        "rating": "4.9", "reviews": 212,
    },
    {
        "id": "blue-pen", "name": "Ballpoint pen set", "category": "Stationery",
        "price": "0.0012", "image": "ballpoint.jpg", "popular": False,
        "description": "A set of smooth-writing ballpoint pens in bright colors for everyday notes.",
        "rating": "4.5", "reviews": 51,
    },
    {
        "id": "sticky-notes", "name": "Sticky note pad", "category": "Stationery",
        "price": "0.0009", "image": "sticky-note.jpg", "popular": False,
        "description": "Bright sticky notes for reminders, page markers, and quick study prompts.",
        "rating": "4.8", "reviews": 88,
    },
    {
        "id": "study-lamp", "name": "LED study lamp", "category": "Electronics",
        "price": "0.035", "image": "study-lamp.jpg", "popular": False,
        "description": "A soft, adjustable desk lamp to brighten your room for evening study.",
        "rating": "4.7", "reviews": 42,
    },
    {
        "id": "bottled-water", "name": "Bottled water", "category": "Snacks",
        "price": "0.0007", "image": "water.jpg", "popular": False,
        "description": "A cool bottle of water for your walk between classes.",
        "rating": "4.6", "reviews": 63,
    },
    {
        "id": "wireless-earbuds", "name": "Wireless earbuds", "category": "Electronics",
        "price": "0.055", "image": "airpod.jpg", "popular": True,
        "description": "Compact wireless earbuds with a charging case for your commute and study playlist.",
        "rating": "4.8", "reviews": 76,
    },
    {
        "id": "scientific-calculator", "name": "Scientific calculator", "category": "Electronics",
        "price": "0.012", "image": "calculator.jpg", "popular": False,
        "description": "A full-featured calculator for problem sets, lab work, and exam prep.",
        "rating": "4.7", "reviews": 52,
    },
    {
        "id": "eraser", "name": "Soft precision eraser", "category": "Stationery",
        "price": "0.0005", "image": "eraser.jpg", "popular": False,
        "description": "A soft, clean-lifting eraser for tidy notes and careful sketching.",
        "rating": "4.5", "reviews": 34,
    },
    {
        "id": "correction-tape", "name": "Correction tape", "category": "Stationery",
        "price": "0.0014", "image": "correction-tape.jpg", "popular": False,
        "description": "Quick-drying correction tape to keep assignments neat and ready to submit.",
        "rating": "4.6", "reviews": 29,
    },
    {
        "id": "headphones", "name": "Over-ear headphones", "category": "Electronics",
        "price": "0.032", "image": "headphones.jpg", "popular": False,
        "description": "Comfortable over-ear headphones for focused listening between classes.",
        "rating": "4.7", "reviews": 48,
    },
    {
        "id": "laptop", "name": "Everyday laptop", "category": "Electronics",
        "price": "0.36", "image": "laptop.jpg", "popular": False,
        "description": "A demo listing for a study laptop, ideal for coursework and campus projects.",
        "rating": "4.8", "reviews": 22,
    },
    {
        "id": "ruler", "name": "Clear measuring ruler", "category": "Stationery",
        "price": "0.0008", "image": "ruler.jpg", "popular": False,
        "description": "A clear 15-centimeter ruler for diagrams, technical drawing, and quick measurements.",
        "rating": "4.4", "reviews": 31,
    },
    {
        "id": "sticker-pack", "name": "Campus sticker pack", "category": "Stationery",
        "price": "0.0025", "image": "stickers.jpg", "popular": False,
        "description": "A colorful pack of stickers to personalize your notebook, laptop, and water bottle.",
        "rating": "4.9", "reviews": 67,
    },
]

PRODUCT_BY_ID = {product["id"]: product for product in PRODUCTS}
CATEGORIES = ["All", "Stationery", "Snacks", "Electronics", "Printing"]
