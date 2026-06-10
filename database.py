from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from datetime import datetime
from bson import ObjectId
from config import MONGO_URI
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        client         = MongoClient(MONGO_URI)
        db             = client["viewsbot"]
        self.users     = db["users"]
        self.projects  = db["auto_projects"]
        self.orders    = db["orders"]

        # Indexes
        self.users.create_index("user_id", unique=True)
        self.projects.create_index([("user_id", ASCENDING), ("channel", ASCENDING)])
        self.orders.create_index("user_id")

    # ─── User CRUD ───────────────────────────────────────────────────────────

    def user_exists(self, user_id: str) -> bool:
        return bool(self.users.find_one({"user_id": str(user_id)}))

    def insert_user(self, user_id: str, name: str, ref_by: str = None):
        try:
            self.users.insert_one({
                "user_id":       str(user_id),
                "name":          name,
                "balance":       0,
                "ref_by":        str(ref_by) if ref_by else None,
                "referred":      0,
                "welcome_bonus": 1,
                "total_refs":    0,
                "subscription":  {},
                "joined":        datetime.utcnow().strftime("%Y-%m-%d"),
            })
        except DuplicateKeyError:
            pass

    def get_user(self, user_id: str) -> dict:
        return self.users.find_one({"user_id": str(user_id)}, {"_id": 0})

    def get_balance(self, user_id: str) -> int:
        user = self.get_user(user_id)
        return int(user.get("balance", 0)) if user else 0

    def add_balance(self, user_id: str, amount: int):
        self.users.update_one(
            {"user_id": str(user_id)},
            {"$inc": {"balance": int(amount)}}
        )

    def cut_balance(self, user_id: str, amount: int):
        self.users.update_one(
            {"user_id": str(user_id)},
            {"$inc": {"balance": -int(amount)}}
        )

    def increment_refs(self, user_id: str):
        self.users.update_one(
            {"user_id": str(user_id)},
            {"$inc": {"total_refs": 1}}
        )

    def get_all_user_ids(self):
        return [u["user_id"] for u in self.users.find({}, {"user_id": 1})]

    def count_users(self) -> int:
        return self.users.count_documents({})

    # ─── Subscription ────────────────────────────────────────────────────────

    def set_subscription(self, user_id: str, daily_amount: int, expiry: datetime):
        self.users.update_one(
            {"user_id": str(user_id)},
            {"$set": {
                "subscription": {
                    "active":       True,
                    "daily_amount": daily_amount,
                    "expiry":       expiry,
                    "started":      datetime.utcnow(),
                }
            }}
        )

    def cancel_subscription(self, user_id: str):
        self.users.update_one(
            {"user_id": str(user_id)},
            {"$set": {"subscription": {"active": False}}}
        )

    def get_subscribed_users(self):
        return list(self.users.find({"subscription.active": True}))

    # ─── Auto Projects ───────────────────────────────────────────────────────

    def add_auto_project(self, user_id: str, channel: str, views_per_post: int):
        self.projects.insert_one({
            "user_id":        str(user_id),
            "channel":        channel,
            "views_per_post": views_per_post,
            "active":         True,
            "created":        datetime.utcnow(),
        })

    def get_auto_projects(self, user_id: str) -> list:
        return list(self.projects.find({"user_id": str(user_id)}))

    def get_active_projects_for_channel(self, channel: str) -> list:
        return list(self.projects.find({"channel": channel, "active": True}))

    def toggle_auto_project(self, project_id: str, user_id: str, active: bool):
        self.projects.update_one(
            {"_id": ObjectId(project_id), "user_id": str(user_id)},
            {"$set": {"active": active}}
        )

    def delete_auto_project(self, project_id: str, user_id: str):
        self.projects.delete_one(
            {"_id": ObjectId(project_id), "user_id": str(user_id)}
        )

    def count_auto_projects(self, user_id: str) -> int:
        return self.projects.count_documents({"user_id": str(user_id)})

    def count_all_auto_projects(self) -> int:
        return self.projects.count_documents({})

    # ─── Orders ──────────────────────────────────────────────────────────────

    def log_order(self, user_id: str, link: str, amount: int, order_id, auto: bool = False):
        self.orders.insert_one({
            "user_id":  str(user_id),
            "link":     link,
            "amount":   amount,
            "order_id": order_id,
            "auto":     auto,
            "time":     datetime.utcnow(),
        })

    def log_admin_order(self, target_uid: str, link: str, amount: int, order_id, admin_id):
        self.orders.insert_one({
            "user_id":  str(target_uid),
            "admin_id": str(admin_id),
            "link":     link,
            "amount":   amount,
            "order_id": order_id,
            "auto":     False,
            "admin":    True,
            "time":     datetime.utcnow(),
        })

    def count_orders(self) -> int:
        return self.orders.count_documents({})


# Singleton
db = Database()

    # ─── Payments ────────────────────────────────────────────────────────────

    def create_payment(self, user_id: str, views: int, amount_inr: float = 0,
                       amount_usd: float = 0, method: str = "", ref: str = "") -> str:
        """Create a pending payment. Returns payment _id as string."""
        result = self.orders.database["payments"].insert_one({
            "user_id":    str(user_id),
            "views":      views,
            "amount_inr": amount_inr,
            "amount_usd": amount_usd,
            "method":     method,
            "ref":        ref,          # UTR / txn ID
            "status":     "pending",    # pending | approved | rejected
            "created":    datetime.utcnow(),
        })
        return str(result.inserted_id)

    def get_payment(self, payment_id: str):
        from bson import ObjectId
        return self.orders.database["payments"].find_one({"_id": ObjectId(payment_id)})

    def update_payment_ref(self, payment_id: str, ref: str):
        from bson import ObjectId
        self.orders.database["payments"].update_one(
            {"_id": ObjectId(payment_id)},
            {"$set": {"ref": ref}}
        )

    def approve_payment(self, payment_id: str):
        from bson import ObjectId
        pay = self.get_payment(payment_id)
        if not pay or pay["status"] != "pending":
            return None
        self.orders.database["payments"].update_one(
            {"_id": ObjectId(payment_id)},
            {"$set": {"status": "approved"}}
        )
        # Credit views
        self.add_balance(pay["user_id"], pay["views"])
        return pay

    def reject_payment(self, payment_id: str):
        from bson import ObjectId
        pay = self.get_payment(payment_id)
        if not pay:
            return None
        self.orders.database["payments"].update_one(
            {"_id": ObjectId(payment_id)},
            {"$set": {"status": "rejected"}}
        )
        return pay

    def get_pending_payments(self):
        return list(self.orders.database["payments"].find({"status": "pending"}))
