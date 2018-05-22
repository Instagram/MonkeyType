# Copyright 2017-present, Facebook, Inc.
# All rights reserved.
"""
Sample code for MonkeyType demonstration exercise at PyCon 2018.

"""
from datetime import datetime
import enum
from typing import (
    Collection, Dict, Generic, List, NamedTuple, NewType, Optional, TypeVar
)


UserId = NewType("UserId", int)
FeedEntryId = NewType("FeedEntryId", int)
InboxEventId = NewType("InboxEventId", int)


class FeedEntry:

    def __init__(
        self, id: FeedEntryId, user_id: UserId, caption: str, published: datetime
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.caption = caption
        self.published = published


class User:

    def __init__(self, id: UserId, name: str, following: List[UserId]) -> None:
        self.id = id
        self.name = name
        self.following = following


class EventType(enum.Enum):
    COMMENTED = "commented"
    FOLLOWED = "followed"
    LIKED = "liked"


class InboxEvent:
    type: EventType

    def __init__(self, id: InboxEventId, user_id: UserId, published: datetime) -> None:
        self.id = id
        self.user_id = user_id
        self.published = published


class CommentedEvent(InboxEvent):
    type = EventType.COMMENTED

    def __init__(
        self,
        id: InboxEventId,
        user_id: UserId,
        published: datetime,
        feedentry_id: FeedEntryId,
        commenter_id: UserId,
        comment_text: str,
    ) -> None:
        super().__init__(id, user_id, published)
        self.feedentry_id = feedentry_id
        self.commenter_id = commenter_id
        self.comment_text = comment_text


class LikedEvent(InboxEvent):
    type = EventType.LIKED

    def __init__(
        self,
        id: InboxEventId,
        user_id: UserId,
        published: datetime,
        feedentry_id: FeedEntryId,
        liker_id: UserId,
    ) -> None:
        super().__init__(id, user_id, published)
        self.feedentry_id = feedentry_id
        self.liker_id = liker_id


class FollowedEvent(InboxEvent):
    type = EventType.FOLLOWED

    def __init__(
        self,
        id: InboxEventId,
        user_id: UserId,
        published: datetime,
        follower_id: UserId,
    ) -> None:
        super().__init__(id, user_id, published)
        self.follower_id = follower_id


class RepoInterface:

    def get_feed_entries_by_ids(
        self, ids: Collection[FeedEntryId]
    ) -> Dict[FeedEntryId, Optional[FeedEntry]]:
        raise NotImplementedError()

    def get_feed_entries_for_user_id(self, user_id: UserId) -> List[FeedEntry]:
        raise NotImplementedError()

    def get_users_by_ids(self, ids: Collection[UserId]) -> Dict[UserId, Optional[User]]:
        raise NotImplementedError()

    def get_inbox_events_for_user_id(self, user_id: UserId) -> List[InboxEvent]:
        raise NotImplementedError()


T = TypeVar("T", bound=InboxEvent)


class AggregatedItem(NamedTuple):
    type: EventType
    text: str
    published: datetime


class AggregatorInterface(Generic[T]):
    type: EventType

    def __init__(self, repo: RepoInterface) -> None:
        self.repo = repo

    def add(self, event: T) -> None:
        pass

    def aggregate(self) -> List[AggregatedItem]:
        return []
