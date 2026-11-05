from app import app, db, User, GlobalInventoryItem, ROLE_ADMIN, ROLE_PROJECT_MANAGER, ROLE_TEAM_LEADER
from werkzeug.security import generate_password_hash

with app.app_context():
    print("Dropping old tables...")
    db.drop_all()
    print("Creating fresh NetSync schema...")
    db.create_all()

    admin_user = User(
        username="admin",
        email="admin@netsync.ph",
        password_hash=generate_password_hash("admin123"),
        role=ROLE_ADMIN
    )
    db.session.add(admin_user)

    catalogue = [
        GlobalInventoryItem(item_name="Panduit Cat6 Cable", category="CAT6 Cable",
            description="Per 1m, incl. testing & 1-yr warranty", unit_price=630, unit_label="meter"),
        GlobalInventoryItem(item_name="Belden Cat6 Cable", category="CAT6 Cable",
            description="Per 1m, incl. testing & 1-yr warranty", unit_price=550, unit_label="meter"),
        GlobalInventoryItem(item_name="Commscope Cat6 Cable", category="CAT6 Cable",
            description="Per 1m, incl. testing & 1-yr warranty", unit_price=560, unit_label="meter"),
        GlobalInventoryItem(item_name="Metal Cable Tray (GI) 50x50mm 1.5mm thick", category="Cable Tray",
            description="Per 2.4m length, galvanized iron", unit_price=2200, unit_label="2.4m length"),
        GlobalInventoryItem(item_name="Panduit Cable Basket", category="Cable Basket",
            description="Per 3m", unit_price=1995, unit_label="3m length"),
        GlobalInventoryItem(item_name="Belden Cable Basket", category="Cable Basket",
            description="Per 3m", unit_price=1965, unit_label="3m length"),
        GlobalInventoryItem(item_name="Commscope Cable Basket", category="Cable Basket",
            description="Per 3m", unit_price=1980, unit_label="3m length"),
    ]
    for item in catalogue:
        db.session.add(item)

    db.session.commit()
    print("Database Reset Successful!")
    print("Log in with Username: admin | Password: admin123")