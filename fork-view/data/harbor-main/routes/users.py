@router.post("/users/invite")
def invite_user(body: Invite):
    return auth.invite(body.email, role=body.role)
