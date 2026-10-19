"""Which PetClinic files implement which synthetic requirement (a hand-made answer key for testing stage 1).

HOW THIS WAS MADE: the requirements in ``petclinic_requirements.py`` were written from the PetClinic code, and this table
was written by reading that code (controllers, validators, templates). It is NOT an expert-labelled gold set: one person
(the assistant), one project, links judged by reading, no second opinion. Use it to compare retrieval models with each
other on a real code base, not to claim absolute accuracy.

Four requirements have no code on purpose (online payment, e-mail reminder, login, database support lives in SQL and
property files, which are not code files here); they have an empty list and are left out of the recall numbers.
"""

JAVA = "src/main/java/org/springframework/samples/petclinic/"
HTML = "src/main/resources/templates/"

GOLD: dict[str, list[str]] = {
    "PC-REQ-001": [JAVA + "owner/OwnerController.java", JAVA + "owner/Owner.java", JAVA + "owner/OwnerRepository.java", HTML + "owners/createOrUpdateOwnerForm.html"],
    "PC-REQ-002": [JAVA + "owner/OwnerController.java", JAVA + "owner/OwnerRepository.java", HTML + "owners/findOwners.html"],
    "PC-REQ-003": [JAVA + "owner/OwnerController.java", JAVA + "owner/OwnerRepository.java", HTML + "owners/ownersList.html"],
    "PC-REQ-004": [JAVA + "owner/OwnerController.java"],
    "PC-REQ-005": [JAVA + "owner/OwnerController.java", HTML + "owners/findOwners.html"],
    "PC-REQ-006": [JAVA + "owner/OwnerController.java", JAVA + "owner/Owner.java", JAVA + "owner/Pet.java", JAVA + "owner/Visit.java", HTML + "owners/ownerDetails.html"],
    "PC-REQ-007": [JAVA + "owner/OwnerController.java", JAVA + "owner/Owner.java", HTML + "owners/createOrUpdateOwnerForm.html"],
    "PC-REQ-008": [JAVA + "owner/PetController.java", JAVA + "owner/Pet.java", JAVA + "owner/PetType.java", JAVA + "owner/PetTypeFormatter.java",
                   JAVA + "owner/PetTypeRepository.java", HTML + "pets/createOrUpdatePetForm.html"],
    "PC-REQ-009": [JAVA + "owner/PetController.java", JAVA + "owner/Pet.java", HTML + "pets/createOrUpdatePetForm.html"],
    "PC-REQ-010": [JAVA + "owner/PetValidator.java", JAVA + "owner/PetController.java", JAVA + "owner/Pet.java"],
    "PC-REQ-011": [JAVA + "owner/PetController.java"],
    "PC-REQ-012": [JAVA + "owner/VisitController.java", JAVA + "owner/Visit.java", HTML + "pets/createOrUpdateVisitForm.html"],
    "PC-REQ-013": [HTML + "owners/ownerDetails.html", JAVA + "owner/Pet.java", JAVA + "owner/Visit.java"],
    "PC-REQ-014": [JAVA + "vet/VetController.java", JAVA + "vet/VetRepository.java", JAVA + "vet/Vet.java", JAVA + "vet/Specialty.java", HTML + "vets/vetList.html"],
    "PC-REQ-015": [JAVA + "vet/VetController.java", JAVA + "vet/Vets.java"],
    "PC-REQ-016": [JAVA + "system/WelcomeController.java", HTML + "welcome.html"],
    "PC-REQ-017": [JAVA + "system/CrashController.java", HTML + "error.html"],
    "PC-REQ-018": [JAVA + "system/WebConfiguration.java", HTML + "fragments/layout.html"],
    "PC-REQ-019": [JAVA + "owner/Owner.java"],
    "PC-REQ-020": [JAVA + "owner/Owner.java"],
    "PC-REQ-021": [JAVA + "system/CacheConfiguration.java", JAVA + "vet/VetRepository.java"],
    "PC-REQ-022": [],
    "PC-REQ-023": [JAVA + "owner/OwnerController.java", JAVA + "owner/PetController.java", JAVA + "owner/VisitController.java"],
    "PC-REQ-024": [],
    "PC-REQ-025": [],
    "PC-REQ-026": [],
}


def gold_pairs(project: str = "spring-petclinic") -> dict[str, set[str]]:
    """Requirement id -> set of code entity ids (``spring-petclinic:<path>``), only requirements that have code."""
    return {rid: {f"{project}:{p}" for p in paths} for rid, paths in GOLD.items() if paths}
