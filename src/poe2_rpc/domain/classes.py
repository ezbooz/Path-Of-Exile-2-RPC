from enum import Enum


class CharacterClass(Enum):
    MERCENARY = "Mercenary"
    MONK = "Monk"
    RANGER = "Ranger"
    SORCERESS = "Sorceress"
    WARRIOR = "Warrior"
    WITCH = "Witch"
    HUNTRESS = "Huntress"

    def get_ascendencies(self) -> list["ClassAscendency"] | None:
        return {
            CharacterClass.MERCENARY: [
                ClassAscendency.WITCHHUNTER,
                ClassAscendency.GEMLING_LEGIONNAIRE,
            ],
            CharacterClass.MONK: [
                ClassAscendency.ACOLYTE_OF_CHAYULA,
                ClassAscendency.INVOKER,
            ],
            CharacterClass.RANGER: [
                ClassAscendency.DEADEYE,
                ClassAscendency.PATHFINDER,
            ],
            CharacterClass.SORCERESS: [
                ClassAscendency.CHRONOMANCER,
                ClassAscendency.STORMWEAVER,
            ],
            CharacterClass.WARRIOR: [
                ClassAscendency.TITAN,
                ClassAscendency.WARBRINGER,
            ],
            CharacterClass.WITCH: [
                ClassAscendency.BLOOD_MAGE,
                ClassAscendency.INFERNALIST,
            ],
            CharacterClass.HUNTRESS: [
                ClassAscendency.RITUALIST,
                ClassAscendency.AMAZON,
            ],
        }.get(self)


class ClassAscendency(Enum):
    WITCHHUNTER = "Witchhunter"
    GEMLING_LEGIONNAIRE = "Gemling Legionnaire"
    ACOLYTE_OF_CHAYULA = "Acolyte of Chayula"
    INVOKER = "Invoker"
    DEADEYE = "Deadeye"
    PATHFINDER = "Pathfinder"
    CHRONOMANCER = "Chronomancer"
    STORMWEAVER = "Stormweaver"
    TITAN = "Titan"
    WARBRINGER = "Warbringer"
    BLOOD_MAGE = "Blood Mage"
    INFERNALIST = "Infernalist"
    RITUALIST = "Ritualist"
    AMAZON = "Amazon"
    SMITH_OF_KITAVA = "Smith of Kitava"
    LICH = "Lich"
    TACTICIAN = "Tactician"

    def get_class(self) -> CharacterClass:
        return {
            ClassAscendency.WITCHHUNTER: CharacterClass.MERCENARY,
            ClassAscendency.GEMLING_LEGIONNAIRE: CharacterClass.MERCENARY,
            ClassAscendency.TACTICIAN: CharacterClass.MERCENARY,
            ClassAscendency.ACOLYTE_OF_CHAYULA: CharacterClass.MONK,
            ClassAscendency.INVOKER: CharacterClass.MONK,
            ClassAscendency.DEADEYE: CharacterClass.RANGER,
            ClassAscendency.PATHFINDER: CharacterClass.RANGER,
            ClassAscendency.CHRONOMANCER: CharacterClass.SORCERESS,
            ClassAscendency.STORMWEAVER: CharacterClass.SORCERESS,
            ClassAscendency.TITAN: CharacterClass.WARRIOR,
            ClassAscendency.WARBRINGER: CharacterClass.WARRIOR,
            ClassAscendency.SMITH_OF_KITAVA: CharacterClass.WARRIOR,
            ClassAscendency.BLOOD_MAGE: CharacterClass.WITCH,
            ClassAscendency.INFERNALIST: CharacterClass.WITCH,
            ClassAscendency.LICH: CharacterClass.WITCH,
            ClassAscendency.RITUALIST: CharacterClass.HUNTRESS,
            ClassAscendency.AMAZON: CharacterClass.HUNTRESS,
        }[self]
