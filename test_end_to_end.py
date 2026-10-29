import io
from app import app
from database import get_db

def run_tests():
    client = app.test_client()

    print("--- 1. Testing Auth Routes ---")
    # Test register
    test_email = "autocheck_test@example.com"
    reg_res = client.post("/api/auth/register", json={
        "name": "Auto Tester",
        "email": test_email,
        "password": "password123"
    })
    print("Register status:", reg_res.status_code, reg_res.get_json())
    assert reg_res.status_code in (201, 400), "Register failed unexpectedly"

    # Test login
    login_res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "password123"
    })
    print("Login status:", login_res.status_code, login_res.get_json())
    assert login_res.status_code == 200, "Login failed"
    user_data = login_res.get_json().get("user")
    assert user_data and user_data.get("email") == test_email

    print("\n--- 2. Testing Items Routes ---")
    # Test create lost item
    lost_res = client.post("/api/items/", json={
        "type": "lost",
        "title": "Unit Test Blue Umbrella",
        "description": "Lost near library with small wooden handle",
        "category": "Accessories",
        "location": "Library",
        "date_lost_found": "2026-10-27"
    })
    print("Create lost item status:", lost_res.status_code, lost_res.get_json())
    assert lost_res.status_code == 201, "Create lost item failed"
    lost_id = lost_res.get_json()["item_id"]

    # Test get all items
    items_res = client.get("/api/items/")
    print("Get items status:", items_res.status_code, f"Count: {len(items_res.get_json())}")
    assert items_res.status_code == 200

    # Test get single item
    item_res = client.get(f"/api/items/{lost_id}")
    print("Get item by id status:", item_res.status_code, item_res.get_json()["title"])
    assert item_res.status_code == 200

    print("\n--- 3. Testing Match Routes ---")
    ranked_res = client.get(f"/api/matches/ranked/{lost_id}")
    print("Get ranked matches status:", ranked_res.status_code)
    ranked_json = ranked_res.get_json()
    print("Ranked matches count:", ranked_json.get("total_matches"))
    assert ranked_res.status_code == 200

    print("\n--- 4. Testing Uploads Route ---")
    from PIL import Image
    img_byte_arr = io.BytesIO()
    img = Image.new('RGB', (100, 100), color='red')
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    up_res = client.post("/api/uploads/", data={
        "image": (img_byte_arr, "test.jpg")
    }, content_type="multipart/form-data")
    print("Upload status:", up_res.status_code, up_res.get_json())
    assert up_res.status_code == 201
    img_path = up_res.get_json()["image_path"]

    # Test static serving of upload
    serve_res = client.get(f"/{img_path}")
    print(f"Serve {img_path} status:", serve_res.status_code)

    print("\n--- 5. Clean up created test items ---")
    conn = get_db()
    conn.execute("DELETE FROM matches WHERE lost_item_id = ?", (lost_id,))
    conn.execute("DELETE FROM items WHERE id = ?", (lost_id,))
    conn.commit()
    conn.close()
    print("Cleanup done.")

if __name__ == "__main__":
    run_tests()
