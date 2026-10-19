# user-profile Specification

Source: change f0-foundation (archived 2026-10-19)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. All scenarios are pytest-testable. Endpoint: `POST /riftbound/profile/update` (JSON, `@validate_json`), session user only. Errors use `{success:false,error,message}`.

## Requirements

### Requirement: PROF-1 Duplicate email is a client error [c]

Changing the email to one already used by ANOTHER account (compared after trim, case-insensitively) MUST return 409 `{success:false,error:"Conflict",message}`, MUST NOT return 500, and MUST leave the user's data unchanged (including when the violation is only detected at commit). Re-submitting the user's own email MUST succeed.

#### Scenario: Taken email
- GIVEN users alice (`a@x.io`) and bob (`b@x.io`), logged in as bob
- WHEN bob posts `{"email": "A@x.io "}`
- THEN status 409 and bob's email is still `b@x.io`

#### Scenario: Own email
- GIVEN logged in as bob
- WHEN bob posts `{"email": "b@x.io"}`
- THEN status 200 `{success:true}`

#### Scenario: Free email
- GIVEN logged in as bob
- WHEN bob posts `{"email": "new@x.io"}`
- THEN status 200 and the email is updated

### Requirement: PROF-2 Password change needs the current password [c]

A request that sets `password` MUST also carry `current_password` that matches the stored hash. Missing `current_password` or a mismatch MUST return 400 `{success:false,error,message}` and keep the old password. Email-only updates do not require it.

#### Scenario: Correct current password
- GIVEN bob with password `oldpass1`
- WHEN bob posts `{"password":"newpass12","current_password":"oldpass1"}`
- THEN status 200, `check_password('newpass12')` is true, `check_password('oldpass1')` is false

#### Scenario: Wrong or missing current password
- GIVEN bob with password `oldpass1`
- WHEN bob posts `{"password":"newpass12"}` or `{"password":"newpass12","current_password":"nope"}`
- THEN each returns 400 and `check_password('oldpass1')` is still true

#### Scenario: Email only
- GIVEN bob
- WHEN bob posts `{"email":"new@x.io"}` without `current_password`
- THEN status 200

#### Scenario: Baseline test adapted
- GIVEN baseline `test_update_password` posts only `{'password': 'newpassword123'}`
- WHEN unit c lands
- THEN that test is updated to also send `current_password: 'testpass123'` (the fixture user's password) and passes; this is the only intended baseline behavior change

### Requirement: PROF-3 Profile update stays authenticated [c]

Anonymous callers MUST get anonymous denial (302 or JSON 401) and never modify data. The `ProfileUpdate` schema MUST keep rejecting invalid emails (no `@`) with 400 `Validation Error`.

#### Scenario: Anonymous
- GIVEN no session
- WHEN `POST /riftbound/profile/update` is sent
- THEN no user row changes and the status is 302 or 401

#### Scenario: Invalid email
- GIVEN a logged-in user
- WHEN they post `{"email":"nope"}`
- THEN status 400 with `error:"Validation Error"`
