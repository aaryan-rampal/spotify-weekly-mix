import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weekly_mix_leftovers import (
    LEFTOVERS_PLAYLIST_NAME,
    MixTracks,
    SyncPlan,
    apply_plan,
    collect_mix_tracks,
    find_or_create_leftovers,
    is_owned_weekly_mix,
    leftover_track_ids,
    load_cache,
    newest_first,
    plan_sync,
    read_mix_tracks,
    save_cache,
)

USER = "aaryan"


def playlist(pid, name, owner=USER, snapshot="s1"):
    return {"id": pid, "name": name, "owner": {"id": owner}, "snapshot_id": snapshot}


def entry(track_id, added_at="2026-10-19T07:00:00Z", field="track", kind="track", local=False):
    return {
        "added_at": added_at,
        field: {"id": track_id, "type": kind, "is_local": local},
    }


class FakeSpotify:
    """Records the playlist calls the sync makes and serves canned pages."""

    def __init__(self, item_pages=None, created_id="new-playlist"):
        self.item_pages = item_pages or {}
        self.created_id = created_id
        self.item_reads = []
        self.calls = []

    def playlist_items(self, playlist_id, limit=100):
        self.item_reads.append(playlist_id)
        pages = self.item_pages[playlist_id]
        return {**pages[0], "_pages": pages, "_index": 0}

    def next(self, page):
        index = page["_index"] + 1
        if index >= len(page["_pages"]):
            return None
        return {**page["_pages"][index], "_pages": page["_pages"], "_index": index}

    def playlist_add_items(self, playlist_id, items, position=None):
        self.calls.append(("add", playlist_id, list(items), position))

    def playlist_remove_all_occurrences_of_items(self, playlist_id, items):
        self.calls.append(("remove", playlist_id, list(items)))

    def user_playlist_create(self, user, name, public, description):
        self.calls.append(("create", user, name, public))
        return {"id": self.created_id}


def page(items, has_next=False):
    return {"items": items, "next": "more" if has_next else None}


# %% Which playlists count


def test_owned_weekly_mix_matches_name_and_owner():
    assert is_owned_weekly_mix(playlist("p", "Weekly Mix 43"), USER)
    assert is_owned_weekly_mix(playlist("p", "Weekly Mix 1"), USER)


def test_rejects_other_owners_and_other_names():
    assert not is_owned_weekly_mix(playlist("p", "Weekly Mix 43", owner="someone"), USER)
    assert not is_owned_weekly_mix(playlist("p", "Weekly Mix 43 (copy)"), USER)
    assert not is_owned_weekly_mix(playlist("p", "weekly mix 43"), USER)
    assert not is_owned_weekly_mix(playlist("p", LEFTOVERS_PLAYLIST_NAME), USER)


# %% Ordering and filtering


def mix(pid, first_added_at, track_ids, snapshot="s1"):
    return MixTracks(pid, snapshot, first_added_at, tuple(track_ids))


def test_newest_first_orders_by_first_added_and_puts_undated_last():
    older = mix("a", "2025-01-06T07:00:00Z", [])
    newer = mix("b", "2026-10-19T07:00:00Z", [])
    undated = mix("c", None, [])
    assert [m.playlist_id for m in newest_first([older, undated, newer])] == ["b", "a", "c"]


def test_leftovers_keep_mix_order_drop_liked_and_dedupe():
    mixes = [mix("new", "2026-10-19", ["t1", "t2", "t3"]), mix("old", "2026-10-12", ["t3", "t4"])]
    assert leftover_track_ids(mixes, liked_ids={"t2"}) == ["t1", "t3", "t4"]


def test_leftovers_empty_when_everything_is_liked():
    assert leftover_track_ids([mix("m", "2026-10-19", ["t1"])], liked_ids={"t1"}) == []


# %% Planning the sync


def test_plan_adds_missing_and_removes_unwanted():
    plan = plan_sync(current_ids=["a", "b", "c"], desired_ids=["d", "a", "c"])
    assert plan == SyncPlan(to_add=("d",), to_remove=("b",), add_at_top=True)


def test_plan_is_empty_when_playlist_already_matches():
    plan = plan_sync(current_ids=["a", "b"], desired_ids=["a", "b"])
    assert plan == SyncPlan(to_add=(), to_remove=(), add_at_top=True)


def test_plan_appends_in_order_when_playlist_is_empty():
    plan = plan_sync(current_ids=[], desired_ids=["a", "b"])
    assert plan == SyncPlan(to_add=("a", "b"), to_remove=(), add_at_top=False)


# %% Applying the plan


def test_apply_inserts_new_tracks_at_top_keeping_their_order():
    sp = FakeSpotify()
    to_add = tuple(f"t{i}" for i in range(150))
    apply_plan(sp, "pl", SyncPlan(to_add=to_add, to_remove=("x",), add_at_top=True))
    assert sp.calls[0] == ("remove", "pl", ["x"])
    adds = [c for c in sp.calls if c[0] == "add"]
    # Later batches go in first so the earlier batch ends up above them.
    assert adds == [("add", "pl", list(to_add[100:]), 0), ("add", "pl", list(to_add[:100]), 0)]


def test_apply_appends_when_playlist_was_empty():
    sp = FakeSpotify()
    apply_plan(sp, "pl", SyncPlan(to_add=("a", "b"), to_remove=(), add_at_top=False))
    assert sp.calls == [("add", "pl", ["a", "b"], None)]


def test_apply_does_nothing_for_an_empty_plan():
    sp = FakeSpotify()
    apply_plan(sp, "pl", SyncPlan(to_add=(), to_remove=(), add_at_top=True))
    assert sp.calls == []


# %% Reading mixes and the snapshot cache


def test_read_mix_tracks_pages_and_skips_non_tracks():
    sp = FakeSpotify(
        item_pages={
            "m": [
                page([entry("t1", "2026-10-19T07:00:05Z"), entry("ep", kind="episode")], True),
                page(
                    [
                        entry("t2", "2026-10-19T07:00:01Z", field="item"),
                        entry("loc", local=True),
                        {"added_at": None, "track": None},
                    ]
                ),
            ]
        }
    )
    result = read_mix_tracks(sp, playlist("m", "Weekly Mix 43", snapshot="s9"))
    assert result == MixTracks("m", "s9", "2026-10-19T07:00:01Z", ("t1", "t2"))


def test_collect_reuses_cached_mix_when_snapshot_unchanged():
    cached = {"m": mix("m", "2026-10-19", ["t1"], snapshot="s1")}
    sp = FakeSpotify()
    mixes, reads = collect_mix_tracks(sp, [playlist("m", "Weekly Mix 43", snapshot="s1")], cached)
    assert (mixes, reads, sp.item_reads) == ([cached["m"]], 0, [])


def test_collect_rereads_mix_when_snapshot_changed():
    cached = {"m": mix("m", "2026-10-19", ["t1"], snapshot="old")}
    sp = FakeSpotify(item_pages={"m": [page([entry("t2")])]})
    mixes, reads = collect_mix_tracks(sp, [playlist("m", "Weekly Mix 43", snapshot="new")], cached)
    assert reads == 1
    assert mixes[0].track_ids == ("t2",)
    assert mixes[0].snapshot_id == "new"


def test_cache_round_trips(tmp_path):
    path = tmp_path / "state" / "leftovers.json"
    mixes = [mix("m", "2026-10-19T07:00:00Z", ["t1", "t2"], snapshot="s1")]
    save_cache(path, mixes)
    assert load_cache(path) == {"m": mixes[0]}


def test_missing_or_unreadable_cache_starts_empty(tmp_path):
    assert load_cache(tmp_path / "missing.json") == {}
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert load_cache(broken) == {}


def test_cache_file_is_plain_json(tmp_path):
    path = tmp_path / "leftovers.json"
    save_cache(path, [mix("m", None, ["t1"])])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mixes"]["m"] == {"snapshot_id": "s1", "first_added_at": None, "track_ids": ["t1"]}


# %% Finding or creating the playlist


def test_finds_existing_leftovers_playlist_owned_by_user():
    sp = FakeSpotify()
    owned = [
        playlist("x", LEFTOVERS_PLAYLIST_NAME, owner="someone"),
        playlist("mine", LEFTOVERS_PLAYLIST_NAME),
    ]
    assert find_or_create_leftovers(sp, USER, owned) == ("mine", False)
    assert sp.calls == []


def test_creates_private_leftovers_playlist_when_missing():
    sp = FakeSpotify(created_id="fresh")
    assert find_or_create_leftovers(sp, USER, [playlist("m", "Weekly Mix 43")]) == ("fresh", True)
    assert sp.calls == [("create", USER, LEFTOVERS_PLAYLIST_NAME, False)]
