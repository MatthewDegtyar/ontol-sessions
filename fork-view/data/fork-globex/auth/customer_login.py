def customer_session(email, code):
    user = db.customer_users.verify(email, code)
    return issue_session(user, scope="portal")
