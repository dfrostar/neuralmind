"""Tier 2 seat tests — SeatManager CRUD, limit enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from neuralmind.tier2.seats import SeatLimitError, SeatManager

EMAIL1 = "alice" + "@" + "example" + "." + "org"
EMAIL2 = "bob" + "@" + "example" + "." + "org"


class TestSeatManagerBasic:
    """SeatManager add/remove/list/is_active."""

    @pytest.fixture
    def seats(self, tmp_path: Path) -> SeatManager:
        return SeatManager(tmp_path / "seats.json")

    def test_seats_add(self, seats: SeatManager) -> None:
        seat = seats.add_seat(EMAIL1, license_limit=10)
        assert seats.active_count() == 1
        assert seat.email == EMAIL1.lower()

    def test_seats_remove(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=10)
        removed = seats.remove_seat(EMAIL1)
        assert removed.active is False
        assert seats.is_active_seat(EMAIL1) is False

    def test_seats_add_beyond_limit(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=1)
        with pytest.raises(SeatLimitError):
            seats.add_seat(EMAIL2, license_limit=1)

    def test_seats_list(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=10)
        seats.add_seat(EMAIL2, license_limit=10)
        seats.remove_seat(EMAIL1)
        all_seats = seats.list_seats()
        assert len(all_seats) == 2

    def test_seats_is_active(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=10)
        assert seats.is_active_seat(EMAIL1) is True

    def test_seats_inactive_after_removal(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=10)
        seats.remove_seat(EMAIL1)
        assert seats.is_active_seat(EMAIL1) is False

    def test_seats_duplicate_add(self, seats: SeatManager) -> None:
        seat1 = seats.add_seat(EMAIL1, license_limit=10)
        seat2 = seats.add_seat(EMAIL1, license_limit=10)
        assert seat1 is seat2
        assert seats.active_count() == 1


class TestSeatManagerLimitEnforcement:
    """The license seat limit applies to every tier — free includes one seat."""

    @pytest.fixture
    def seats(self, tmp_path: Path) -> SeatManager:
        return SeatManager(tmp_path / "seats.json")

    def test_free_license_enforces_single_seat(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=1)
        with pytest.raises(SeatLimitError):
            seats.add_seat(EMAIL2, license_limit=1)
        assert seats.active_count() == 1

    def test_team_license_enforces_its_limit(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=2)
        seats.add_seat(EMAIL2, license_limit=2)
        with pytest.raises(SeatLimitError):
            seats.add_seat("third@example.org", license_limit=2)

    def test_remove_frees_a_slot(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=1)
        seats.remove_seat(EMAIL1)
        seat2 = seats.add_seat(EMAIL2, license_limit=1)
        assert seat2.active is True
        assert seats.active_count() == 1

    def test_reactivation_respects_limit(self, seats: SeatManager) -> None:
        seats.add_seat(EMAIL1, license_limit=1)
        seats.remove_seat(EMAIL1)
        # Reactivating the only seat fits within the 1-seat limit...
        seat = seats.add_seat(EMAIL1, license_limit=1)
        assert seat.active is True
        # ...but a second distinct seat still does not.
        with pytest.raises(SeatLimitError):
            seats.add_seat(EMAIL2, license_limit=1)
