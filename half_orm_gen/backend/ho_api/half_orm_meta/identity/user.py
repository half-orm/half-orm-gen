"""half_orm_meta.identity.user — federated user identity.

Hand-maintained (not generated — half_orm_meta tables never get a
generated per-table module in an end-user project, see
half_orm_dev/modules.py's guards). Registered against a Model instance by
half_orm_meta.register_all(model), after which model.get_relation_class(...)
and model.classes() both return this class (half_orm.relation_factory
checks the model's own class registry before building a generic one).
"""

import uuid

from half_orm.model import register_class
from litestar.exceptions import HTTPException

from half_orm_gen.tools import api_post, api_get
from half_orm_gen.backend.litestar.v2.jwt_tokens import sign_token

#: (schema, table) — the single source of truth for "this is the identity
#: user resource", used wherever code needs to recognize it generically
#: (FK-target detection in the frontend generators, the reconcile_catalog
#: sync, etc.) instead of a duplicated literal tuple.
RESOURCE = ('half_orm_meta.identity', 'user')

#: Never exposed over the API regardless of what CRUD_ACCESS an admin
#: configures — read generically by runtime.py the same way it reads a
#: generated business module's API_EXCLUDED_FIELDS.
API_EXCLUDED_FIELDS = ['password_hash']

#: Read-only over the generic CRUD API: no POST/PUT/DELETE handlers are
#: registered for this resource (writes happen through the local-auth /
#: federation login flows instead — see ho_api/local_auth.py,
#: ho_api/federation.py). Read generically by runtime.py.
READ_ONLY = True


def build_class(model):
    """Build and register the User relation class for this model instance."""
    base = model.get_relation_class('"half_orm_meta.identity"."user"')

    class User(base):
        @classmethod
        async def authenticate(cls, email: str, password: str) -> str | None:
            """Verify email/password against password_hash (bcrypt).

            Returns the user's id (as str), or None if there's no match —
            unknown email, no password set (e.g. an identity whose origin
            is another peer — see origin_peer_id), or wrong password. Used
            by ho_api/local_auth.py's default (HO_LOCAL_AUTH=db) check.
            """
            import bcrypt

            rows = await cls(email=email).ho_aselect('id', 'password_hash')
            if not rows:
                return None
            row = rows[0]
            stored_hash = row.get('password_hash')
            if not stored_hash:
                return None
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                return None
            return str(row['id'])

        @classmethod
        async def upsert_from_federation(
            cls, user_id, origin_peer_id, name: str | None, email: str | None, now,
        ) -> None:
            """Create or refresh a federated identity's local row on a
            successful delegated login. Never sets password_hash — a
            federated identity authenticates via its origin peer's token,
            not a local password (see ho_api/federation.py).
            """
            existing = await cls(id=user_id).ho_aselect('id')
            if existing:
                await cls(id=user_id).ho_aupdate(last_seen_at=now)
            else:
                await cls(
                    id=user_id, origin_peer_id=origin_peer_id, name=name, email=email,
                    first_seen_at=now, last_seen_at=now,
                ).ho_ainsert()

        @classmethod
        async def create_local(cls, name: str, email: str, password: str) -> str:
            """Create a new local user (bcrypt-hashed password).

            Raises ValueError if the email is already registered. Returns
            the new user's id (str).
            """
            import bcrypt

            existing = await cls(email=email).ho_aselect('id')
            if existing:
                raise ValueError('Email already registered')
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_id = str(uuid.uuid4())
            await cls(
                id=user_id, name=name, email=email, password_hash=password_hash,
            ).ho_ainsert()
            return user_id

        @classmethod
        async def name_for(cls, user_id) -> str | None:
            rows = await cls(id=user_id).ho_aselect('name')
            return rows[0]['name'] if rows else None

        @classmethod
        async def list_all(cls) -> list:
            return await cls().ho_aselect('id', 'name')

        # ------------------------------------------------------------------
        # Default local-auth routes (POST /auth/signup, POST /auth/login,
        # GET /ho_users) — discovered automatically (half_orm_gen.tools.
        # api_post/api_get) by runtime.py's build_crud_app, no scaffolding
        # needed. Backed by half_orm_meta.identity.user — the framework's
        # own answer to "how do users log in", not project-specific code.
        #
        # A project that wants a *different* auth mechanism entirely
        # doesn't override these: it overrides the authenticate() function
        # itself, via ho_api/custom/local_auth.py (see
        # custom/local_auth.py.example) — these three routes keep working
        # unchanged, backed by whatever authenticate() ends up doing.
        # ------------------------------------------------------------------

        @api_post('/auth/signup')
        async def signup(self, data: dict) -> dict:
            """Create a new local user. The first signup becomes admin."""
            email    = (data.get('email') or '').strip()
            name     = (data.get('name') or '').strip()
            password = data.get('password') or ''
            if not email or not name or not password:
                raise HTTPException(status_code=400, detail='name, email and password required')

            cls = self.__class__
            try:
                user_id = await cls.create_local(name, email, password)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))

            UserRole = cls._ho_model.get_relation_class('"half_orm_meta.api".user_role')
            role_name = 'connected' if await UserRole.has_admin() else 'admin'
            await UserRole.grant(user_id, role_name)
            return {'token': sign_token(user_id, [role_name], name, email)}

        @api_post('/auth/login')
        async def login(self, data: dict) -> dict:
            """Real local login: checks the password against this table."""
            email    = (data.get('email') or '').strip()
            password = data.get('password') or ''
            if not email or not password:
                raise HTTPException(status_code=400, detail='email and password required')

            cls = self.__class__
            user_id = await cls.authenticate(email, password)
            if not user_id:
                raise HTTPException(status_code=401, detail='Invalid email or password')

            name = await cls.name_for(user_id)
            UserRole = cls._ho_model.get_relation_class('"half_orm_meta.api".user_role')
            roles = await UserRole.roles_for(user_id)
            return {'token': sign_token(user_id, roles, name, email)}

        @api_get('/ho_users')
        async def list_with_admin_flag(self) -> list:
            """Return all known users (local + federated-in) with their admin flag."""
            cls = self.__class__
            users = await cls.list_all()
            UserRole = cls._ho_model.get_relation_class('"half_orm_meta.api".user_role')
            admin_ids = await UserRole.admin_ids()
            return [
                {
                    'id': str(u['id']), 'name': u['name'] or '(unnamed)',
                    'is_admin': str(u['id']) in admin_ids,
                }
                for u in users
            ]

    return register_class(User)
