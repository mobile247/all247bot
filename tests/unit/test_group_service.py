"""
Unit tests for GroupService.
"""

import pytest

from bot.services.group_service import GroupService

pytestmark = pytest.mark.asyncio


async def test_activate_new_group(db_path):
    svc = GroupService(db_path)
    result = await svc.activate(group_id=-100, activated_by=1)
    assert result is True


async def test_activate_already_active_returns_false(db_path):
    svc = GroupService(db_path)
    await svc.activate(group_id=-100, activated_by=1)
    result = await svc.activate(group_id=-100, activated_by=1)
    assert result is False


async def test_is_active_false_before_setup(db_path):
    svc = GroupService(db_path)
    assert await svc.is_active(-100) is False


async def test_is_active_true_after_activate(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    assert await svc.is_active(-100) is True


async def test_deactivate(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.deactivate(-100, deactivated_by=1)
    assert await svc.is_active(-100) is False


async def test_get_config_defaults_for_unknown_group(db_path):
    svc = GroupService(db_path)
    config = await svc.get_config(-999)
    assert config == {
        "cooldown": 0,
        "delete_trigger": "off",
        "invite_expiry": 24,
        "mention_mode": "display_name",
        "restrict_all_to_admins": "off",
    }


async def test_get_config_after_activate(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    config = await svc.get_config(-100)
    assert config["cooldown"] == 0
    assert config["delete_trigger"] == "off"
    assert config["restrict_all_to_admins"] == "off"
    assert config["mention_mode"] == "display_name"


async def test_update_config_cooldown(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.update_config(-100, "cooldown", "30", changed_by=1)
    config = await svc.get_config(-100)
    assert config["cooldown"] == 30


async def test_update_config_delete_trigger_on(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.update_config(-100, "delete_trigger", "on", changed_by=1)
    assert (await svc.get_config(-100))["delete_trigger"] == "on"


async def test_update_config_restrict_all_to_admins(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.update_config(-100, "restrict_all_to_admins", "on", changed_by=1)
    assert (await svc.get_config(-100))["restrict_all_to_admins"] == "on"


async def test_update_config_mention_mode_username(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.update_config(-100, "mention_mode", "username", changed_by=1)
    assert (await svc.get_config(-100))["mention_mode"] == "username"


async def test_update_config_invalid_key_raises(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    with pytest.raises(ValueError, match="Invalid config key"):
        await svc.update_config(-100, "nonexistent_key", "val", changed_by=1)


async def test_update_config_invalid_value_raises(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    with pytest.raises(ValueError, match="Invalid value"):
        await svc.update_config(-100, "mention_mode", "emoji", changed_by=1)


async def test_update_config_invalid_value_raises_lists_valid_options(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    with pytest.raises(ValueError) as exc_info:
        await svc.update_config(-100, "delete_trigger", "maybe", changed_by=1)
    assert "off" in str(exc_info.value)
    assert "on" in str(exc_info.value)


async def test_update_config_cooldown_negative_raises(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    with pytest.raises(ValueError, match=">= 0"):
        await svc.update_config(-100, "cooldown", "-5", changed_by=1)


async def test_update_config_cooldown_non_int_raises(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    with pytest.raises(ValueError, match="integer"):
        await svc.update_config(-100, "cooldown", "fast", changed_by=1)


async def test_reactivate_after_deactivate(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.deactivate(-100, deactivated_by=1)
    result = await svc.activate(-100, activated_by=2)
    assert result is True
    assert await svc.is_active(-100) is True


async def test_activate_stores_title(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1, title="My Group")
    groups = await svc.get_all_groups()
    assert groups[0]["title"] == "My Group"


async def test_update_title_stores_title(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.update_title(-100, "Renamed Group")
    groups = await svc.get_all_groups()
    assert groups[0]["title"] == "Renamed Group"


async def test_update_title_replaces_existing(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1, title="Old Name")
    await svc.update_title(-100, "New Name")
    groups = await svc.get_all_groups()
    assert groups[0]["title"] == "New Name"


async def test_get_all_groups_returns_active_and_inactive(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1, title="Active Group")
    await svc.activate(-200, activated_by=1, title="Inactive Group")
    await svc.deactivate(-200, deactivated_by=1)
    groups = await svc.get_all_groups()
    assert len(groups) == 2
    active = next(g for g in groups if g["group_id"] == -100)
    inactive = next(g for g in groups if g["group_id"] == -200)
    assert active["is_active"] is True
    assert inactive["is_active"] is False


async def test_migrate_moves_group_and_updates_cache(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1, title="Old Group")
    # Warm the cache
    assert await svc.is_active(-100) is True

    result = await svc.migrate(-100, -200)

    assert result is True
    assert await svc.is_active(-100) is False
    assert await svc.is_active(-200) is True


async def test_migrate_preserves_config(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.update_config(-100, "cooldown", "60", changed_by=1)

    await svc.migrate(-100, -200)

    config = await svc.get_config(-200)
    assert config["cooldown"] == 60


async def test_migrate_returns_false_when_old_id_not_found(db_path):
    svc = GroupService(db_path)
    result = await svc.migrate(-999, -200)
    assert result is False


async def test_migrate_returns_false_when_new_id_already_exists(db_path):
    svc = GroupService(db_path)
    await svc.activate(-100, activated_by=1)
    await svc.activate(-200, activated_by=1)
    result = await svc.migrate(-100, -200)
    assert result is False
