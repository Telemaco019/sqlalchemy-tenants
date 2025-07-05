from faker import Faker

fake = Faker()

TEST_TENANT_PREFIX = "test_"


def new_tenant() -> str:
    return f"{TEST_TENANT_PREFIX}{str(fake.uuid4())}"
