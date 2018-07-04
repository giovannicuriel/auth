from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy import ForeignKey, Enum, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

import enum
import datetime
import kongUtils

from .inputConf import UserLimits, PermissionLimits, GroupLimits
from .flaskAlchemyInit import db
from .materialized_view_factory import create_mat_view
from .materialized_view_factory import refresh_mat_view

from auth.  database.flaskAlchemyInit import HTTPRequestError


class PermissionEnum(enum.Enum):
    permit = 'permit'
    deny = 'deny'
    notApplicable = 'notApplicable'


class PermissionTypeEnum(enum.Enum):
    system = 'system'
    api = 'api'
    notApplicable = 'notApplicable'


# Model for the database tables
class Permission(db.Model):
    __tablename__ = 'permission'

    # fields that can be filled by user input
    fillable = ['name', 'path', 'method', 'permission', 'type']

    def as_dict(self):
        """
        Creates a dictionary using the contents of this class.
        :return: A dictionary
        """
        tmp_dict = {
                    c.name: getattr(self, c.name)
                    for c in self.__table__.columns
                  }
        if type(tmp_dict['permission']) != str:
            tmp_dict['permission'] = tmp_dict['permission'].value

        if (not tmp_dict['type'] is None) and type(tmp_dict['type']) != str:
            tmp_dict['type'] = tmp_dict['type'].value
        elif tmp_dict['type'] is None:
            tmp_dict['type'] = PermissionTypeEnum.api.value

        return tmp_dict

    def safe_dict(self):
        return self.as_dict()

    @staticmethod
    def get_by_name_or_id(name_id: str):
        """
        Returns a permission with a particular name or ID
        :param name_id: The ID from the permission to be retrieved
        :return: The permission
        """
        try:
            return db.session.query(Permission). \
                        filter_by(id=int(name_id)).one()
        except ValueError:
            return db.session.query(Permission).filter_by(name=name_id).one()

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(PermissionLimits.path), nullable=False)
    name = Column(String(PermissionLimits.name), nullable=False,
                  unique=True, index=True)
    method = Column(String(PermissionLimits.method), nullable=False)
    permission = Column(Enum(PermissionEnum), nullable=False)
    type = Column(Enum(PermissionTypeEnum), nullable=False, default=PermissionTypeEnum.api)

    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(Integer, nullable=False)

    users = relationship('User', secondary='user_permission')
    groups = relationship('Group',
                          secondary='group_permission')


class User(db.Model):
    __tablename__ = 'user'
    # Fields that should not be returned to the user
    sensibleFields = ['hash', 'salt', 'secret', 'kongId', 'key']

    # Fields that can be filled by user input
    fillable = ['name', 'username', 'service', 'email', 'profile']

    # serialize class as python dictionary
    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def safe_dict(self):
        """
        Generates a safe dict from this User.
        This new dictionary is serializable and it doesn't have any sensible fields (such as password)
        :return: A serializable dictionary without all sensible user fields.
        """
        return {
                c.name: str(getattr(self, c.name))
                for c in self.__table__.columns
                if c.name not in self.sensibleFields
            }

    def reset_token(self):
        kong_data = kongUtils.reset_kong_secret(self.username, self.kongId)

        if kong_data is not None:
            self.secret = kong_data['secret']
            self.key = kong_data['key']
            self.kongId = kong_data['kongid']

    @staticmethod
    def get_by_name_or_id(name_or_id: str):
        """
        Returns a permission with a particular name or ID
        :param name_or_id: The ID from the permission to be retrieved
        :return: The permission
        """
        # TODO This function might be better placed somewhere else. Is it a responsibility of User model
        # to perform searches in the database?
        try:
            try:
                integer_id = int(name_or_id)
                return db.session.query(User).filter_by(id=integer_id).one()
            except ValueError:
                return db.session.query(User).filter_by(username=name_or_id).one()
        except NoResultFound:
            raise HTTPRequestError(404, "Unknown user id")

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(UserLimits.name), nullable=False)
    username = Column(String(UserLimits.username), unique=True, nullable=False)
    service = Column(String(UserLimits.service), nullable=False)
    email = Column(String(UserLimits.email), nullable=False, unique=True)
    profile = Column(String(UserLimits.profile), nullable=False)
    hash = Column(String, nullable=True)
    salt = Column(String, nullable=True)

    # These fields are configured by kong after user creation
    secret = Column(String, nullable=False)
    key = Column(String, nullable=False)
    kongId = Column(String, nullable=False)

    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(Integer, nullable=False)

    # Table Relationships
    permissions = relationship('Permission',
                               secondary='user_permission')
    groups = relationship('Group', secondary='user_group')


class Group(db.Model):
    __tablename__ = 'group'

    fillable = ['name', 'description']

    # serialize class as python dictionary
    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def safe_dict(self):
        return self.as_dict()

    def get_by_name_or_id(nameOrId):
        # TODO This function might be better placed somewhere else.
        try:
            return db.session.query(Group).filter_by(id=int(nameOrId)).one()
        except ValueError:
            return db.session.query(Group).filter_by(name=nameOrId).one()

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(GroupLimits.name), unique=True, nullable=False)
    description = Column(String(GroupLimits.description), nullable=True)

    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(Integer, nullable=False)

    # Table relationships
    permissions = relationship('Permission',
                               secondary='group_permission')
    users = relationship('User', secondary='user_group')


class UserPermission(db.Model):
    __tablename__ = 'user_permission'
    permission_id = Column(Integer,
                           ForeignKey('permission.id'),
                           primary_key=True, index=True)
    user_id = Column(Integer,
                     ForeignKey('user.id'),
                     primary_key=True, index=True)


class GroupPermission(db.Model):
    __tablename__ = 'group_permission'
    permission_id = Column(Integer,
                           ForeignKey('permission.id'),
                           primary_key=True, index=True)
    group_id = Column(Integer,
                      ForeignKey('group.id'),
                      primary_key=True, index=True)


class UserGroup(db.Model):
    __tablename__ = 'user_group'
    user_id = Column(Integer,
                     ForeignKey('user.id'),
                     primary_key=True, index=True)
    group_id = Column(Integer,
                      ForeignKey('group.id'),
                      primary_key=True, index=True)


# table to keep the temporary password reset links
class PasswordRequest(db.Model):
    __tablename__ = 'passwd_request'

    user_id = Column(Integer, primary_key=True, autoincrement=False)
    link = Column(String, nullable=False, index=True)
    created_date = Column(DateTime, default=datetime.datetime.utcnow)


class MVUserPermission(db.Model):
    selectClause = db.select([UserPermission.user_id,
                              Permission.id,
                              Permission.path,
                              Permission.method,
                              Permission.permission,
                              Permission.type, ]
                             ).select_from(db.join(UserPermission, Permission))

    __table__ = create_mat_view('mv_user_permission',
                                selectClause)

    # SQLAlchemy require a unique primary key to map ORM objects
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'id'),
        {},
    )

    def refresh(concurrently=False):
        refresh_mat_view('mv_user_permission', concurrently)


db.Index('mv_user_permission_user_idx', MVUserPermission.user_id, unique=False)


class MVGroupPermission(db.Model):
    selectClause = db.select([GroupPermission.group_id,
                              Permission.id,
                              Permission.path,
                              Permission.method,
                              Permission.permission,
                              Permission.type,]
                             ).select_from(db.join(GroupPermission,
                                                   Permission))

    __table__ = create_mat_view('mv_group_permission',
                                selectClause)

    # SQLAlchemy require a unique primary key to map ORM objects
    __table_args__ = (
        PrimaryKeyConstraint('group_id', 'id'),
        {},
    )

    def refresh(concurrently=False):
        refresh_mat_view('mv_group_permission', concurrently)


db.Index('mv_group_permission_user_idx',
         MVGroupPermission.group_id, unique=False)
