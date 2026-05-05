"""Tests for domain/classes.py — CharacterClass and ClassAscendency enums."""

from poe2_rpc.domain.classes import CharacterClass, ClassAscendency


class TestCharacterClass:
    def test_all_base_classes_present(self) -> None:
        names = {m.name for m in CharacterClass}
        assert names == {
            "MERCENARY",
            "MONK",
            "RANGER",
            "SORCERESS",
            "WARRIOR",
            "WITCH",
            "HUNTRESS",
        }

    def test_enum_values_match_ingame_strings(self) -> None:
        assert CharacterClass.MERCENARY.value == "Mercenary"
        assert CharacterClass.MONK.value == "Monk"
        assert CharacterClass.RANGER.value == "Ranger"
        assert CharacterClass.SORCERESS.value == "Sorceress"
        assert CharacterClass.WARRIOR.value == "Warrior"
        assert CharacterClass.WITCH.value == "Witch"
        assert CharacterClass.HUNTRESS.value == "Huntress"

    def test_get_ascendencies_returns_correct_list(self) -> None:
        assert ClassAscendency.WITCHHUNTER in CharacterClass.MERCENARY.get_ascendencies()
        assert ClassAscendency.GEMLING_LEGIONNAIRE in CharacterClass.MERCENARY.get_ascendencies()
        assert ClassAscendency.TITAN in CharacterClass.WARRIOR.get_ascendencies()
        assert ClassAscendency.WARBRINGER in CharacterClass.WARRIOR.get_ascendencies()
        assert ClassAscendency.RITUALIST in CharacterClass.HUNTRESS.get_ascendencies()
        assert ClassAscendency.AMAZON in CharacterClass.HUNTRESS.get_ascendencies()


class TestClassAscendency:
    def test_all_ascendencies_present(self) -> None:
        names = {m.name for m in ClassAscendency}
        assert names == {
            "WITCHHUNTER",
            "GEMLING_LEGIONNAIRE",
            "ACOLYTE_OF_CHAYULA",
            "INVOKER",
            "DEADEYE",
            "PATHFINDER",
            "CHRONOMANCER",
            "STORMWEAVER",
            "TITAN",
            "WARBRINGER",
            "BLOOD_MAGE",
            "INFERNALIST",
            "RITUALIST",
            "AMAZON",
            "SMITH_OF_KITAVA",
            "LICH",
            "TACTICIAN",
        }

    def test_enum_values_match_ingame_strings(self) -> None:
        assert ClassAscendency.WITCHHUNTER.value == "Witchhunter"
        assert ClassAscendency.GEMLING_LEGIONNAIRE.value == "Gemling Legionnaire"
        assert ClassAscendency.ACOLYTE_OF_CHAYULA.value == "Acolyte of Chayula"
        assert ClassAscendency.INVOKER.value == "Invoker"
        assert ClassAscendency.DEADEYE.value == "Deadeye"
        assert ClassAscendency.PATHFINDER.value == "Pathfinder"
        assert ClassAscendency.CHRONOMANCER.value == "Chronomancer"
        assert ClassAscendency.STORMWEAVER.value == "Stormweaver"
        assert ClassAscendency.TITAN.value == "Titan"
        assert ClassAscendency.WARBRINGER.value == "Warbringer"
        assert ClassAscendency.BLOOD_MAGE.value == "Blood Mage"
        assert ClassAscendency.INFERNALIST.value == "Infernalist"
        assert ClassAscendency.RITUALIST.value == "Ritualist"
        assert ClassAscendency.AMAZON.value == "Amazon"
        assert ClassAscendency.SMITH_OF_KITAVA.value == "Smith of Kitava"
        assert ClassAscendency.LICH.value == "Lich"
        assert ClassAscendency.TACTICIAN.value == "Tactician"

    def test_get_class_maps_ascendency_to_base_class(self) -> None:
        assert ClassAscendency.WITCHHUNTER.get_class() == CharacterClass.MERCENARY
        assert ClassAscendency.GEMLING_LEGIONNAIRE.get_class() == CharacterClass.MERCENARY
        assert ClassAscendency.TACTICIAN.get_class() == CharacterClass.MERCENARY
        assert ClassAscendency.ACOLYTE_OF_CHAYULA.get_class() == CharacterClass.MONK
        assert ClassAscendency.INVOKER.get_class() == CharacterClass.MONK
        assert ClassAscendency.DEADEYE.get_class() == CharacterClass.RANGER
        assert ClassAscendency.PATHFINDER.get_class() == CharacterClass.RANGER
        assert ClassAscendency.CHRONOMANCER.get_class() == CharacterClass.SORCERESS
        assert ClassAscendency.STORMWEAVER.get_class() == CharacterClass.SORCERESS
        assert ClassAscendency.TITAN.get_class() == CharacterClass.WARRIOR
        assert ClassAscendency.WARBRINGER.get_class() == CharacterClass.WARRIOR
        assert ClassAscendency.SMITH_OF_KITAVA.get_class() == CharacterClass.WARRIOR
        assert ClassAscendency.BLOOD_MAGE.get_class() == CharacterClass.WITCH
        assert ClassAscendency.INFERNALIST.get_class() == CharacterClass.WITCH
        assert ClassAscendency.LICH.get_class() == CharacterClass.WITCH
        assert ClassAscendency.RITUALIST.get_class() == CharacterClass.HUNTRESS
        assert ClassAscendency.AMAZON.get_class() == CharacterClass.HUNTRESS
