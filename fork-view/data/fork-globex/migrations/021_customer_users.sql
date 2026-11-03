CREATE TABLE customer_users (
  id UUID PRIMARY KEY,
  customer_id UUID NOT NULL REFERENCES customers(id),
  email TEXT NOT NULL UNIQUE
);
