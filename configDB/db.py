from pymongo import MongoClient

client = MongoClient(
    "mongodb://root:myPassword@localhost:27017/social_db?authSource=admin"
)

db = client.social_db

result = db.test_collection.insert_one({
    "name": "MongoDB Test",
    "status": "connection working"
})

print(result.inserted_id)
db.test_collection.insertOne({
    source: "mongosh",
    status: "manual insert works"
})
