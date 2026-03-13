# bots/ardayda_bot/text.py

# ---------- REGISTRATION ----------

REG_NAME = (
    "👋 Welcome!\n\n"
    "Please enter your *full name* to complete registration."
)

REG_SUCCESS = (
    "✅ Registration completed successfully.\n\n"
    "You can now upload and search PDFs using the menu below."
)

REG_IN_PROGRESS_BLOCK = (
    "⚠️ Registration is still in progress.\n"
    "Please complete it before using other features."
)

# School data by region (used in registration)
form_four_schools_by_region = {
    "BARI": [
        "Bandar Qasim",
        "Bari",
        "Garisa",
        "Salahudin",
        "Ras Asayr Bosaso",
        "Omar bin Abdazis",
        "Bosaso Public",
        "Bender Siyaad Qaw",
        "White Tower",
        "Xalane Bosaso",
        "Iftiin Bosaso",
        "Sayid Mohamed Bosaso",
        "Xamdan",
        "Ganaane",
        "Dr Ahmed Bosaso",
        "Iman Nawawi Bosaso",
        "Ugas Yasin",
        "Imam shafie Bosaso",
        "Mocalin Jama Bosaso",
        "Najax",
        "Biyo kulule Bosaso",
        "Haji Yasin",
        "Girible",
        "Mohamed Awale",
        "Haji Salad",
        "Carta",
        "Jaamu Maalik",
        "Eldahir"
    ],
    "NUGAAL": [
        "Imamu Nawawi Garowe F4",
        "DR. Ahmed Garowe F4",
        "Awr Culus F4",
        "Sh. Hamid F4",
        "Nugal F4",
        "Daawad Garowe F4",
        "Gambol F4",
        "Al-Xikma Garowe F4",
        "Al Waxa F4",
        "Kobciye F4",
        "Alculum F4",
        "Xar xaar F4",
        "Dr ahmed Burtinle F4",
        "Burtinle F4",
        "Muntada Burtinle F4",
        "Xasbahalle F4",
        "Sare Qarxis F4",
        "Sare Eyl F4",
        "Sare Sinujjil F4",
        "Sare Negeye F4",
        "Sare Usgure F4",
        "Sare Yoonbays F4",
        "Sare Jalam F4"
    ],
    "KARKAAR": [
        "Qoton",
        "Dhuudo",
        "Dhudhub",
        "Humbays",
        "Qarrasoor",
        "Hidda",
        "Uurjire",
        "Sheerbi",
        "Suldaan Mubarak (Yeka)",
        "Al-Muntada",
        "Ali Afyare",
        "Kubo",
        "Xaaji Aaden",
        "Xaaji Osman"
    ],
    "MUDUG": [
        "1st August",
        "Africa",
        "Dr.Ahmed Galkoio",
        "A.A.Sharmarke",
        "Yamays",
        "Ilays galkaoi",
        "Beyra",
        "Garsoor",
        "Omar Samatar",
        "Haji Ali Bihi",
        "Agoonta Qaran F4",
        "Al-xigma",
        "Hala booqad",
        "Haji Dirie",
        "Yasin Nor",
        "Sare Bacaaadwayn F4",
        "Bacadweyn",
        "Hema",
        "Barbarshe",
        "Bursalah",
        "Golden 18+",
        "Hope",
        "GECPD Xarlo",
        "Cagaraan F4",
        "Sare Garacad",
        "Balli busle F4",
        "Sare Jarriban",
        "Sare Galdogob"
    ],
    "HAYLAAN": [
        "Sare Dhahar Public",
        "Kala-dhac",
        "Salaxudin-Dhahar",
        "Buraan",
        "Dalmar Qol",
        "Damalla Xagarre",
        "Sare Damalla xagarre",
        "Sare Shimbiraale"
    ],
    "RAAS CASAYR": [
        "Maxamed Xuseen",
        "Bareeda",
        "Caluula",
        "Xabbob"
    ],
    "SANAAG": [
        "Al Furqan Badhan",
        "Al-Nuur Badhan",
        "Al-Rahma Badhan",
        "Badhan Sec",
        "Farax-cadde",
        "Hadaftimo",
        "Yubbe",
        "Armale",
        "Rad",
        "Midigale"
    ]
}

SUBJECTS = ["Math", "Physics", "Chemistry", "Biology", "ICT", "Arabic", "Islamic", "English", "Somali", "G.P", "Geography", "History", "Agriculture", "Business"]
TAGS = ["Exam", "Notes", "Summary", "Assignment", "Chapter Reviews"]
# ---------- GENERAL ----------

HOME_WELCOME = (
    "🏠 *Main Menu*\n\n"
    "Choose what you want to do:"
)

CANCELLED = (
    "❌ Operation cancelled.\n\n"
    "You are back at the main menu."
)

SESSION_EXPIRED = (
    "⚠️ This session has expired.\n"
    "Please start again from the main menu."
)

CONFLICT_UPLOAD = (
    "⚠️ You are currently uploading a PDF.\n"
    "Finish it or tap ❌ Cancel before doing something else."
)

CONFLICT_SEARCH = (
    "⚠️ You are currently searching.\n"
    "Finish it or tap ❌ Cancel before starting a new action."
)

UNKNOWN_INPUT = (
    "ℹ️ Please use the buttons provided.\n"
    "\n..."
)


# ---------- UPLOAD FLOW ----------

UPLOAD_START = (
    "📤 *Upload PDF*\n\n"
    "Please send your PDF file."
)

UPLOAD_INVALID_FILE = (
    "❌ Invalid file.\n"
    "Please send a valid *PDF document*."
)

UPLOAD_ALREADY_EXISTS = (
    "⚠️ This PDF already exists in the system.\n"
    "Upload cancelled."
)

UPLOAD_SUBJECT = (
    "📝 *Choose Subject*\n\n"
    "Select the subject for this PDF:"
)

UPLOAD_TAGS = (
    "🏷️ *Select Tags*\n\n"
    "You can select multiple tags.\n"
    "Tap ⬆️ Upload PDF when done."
)

UPLOAD_SUCCESS = (
    "🎉 *Upload Completed!*\n\n"
    "Your PDF has been successfully uploaded."
)

UPLOAD_FAILED = (
    "❌ Upload failed due to an internal error.\n"
    "Please try again later."
)


# ---------- SEARCH FLOW ----------

SEARCH_START = (
    "🔍 *Search PDFs*\n\n"
    "Select a subject to search:"
)

SEARCH_NO_RESULTS = (
    "😕 No PDFs found for the selected tags."
)

SEARCH_RESULTS = (
    "📚 *Search Results*\n\n"
    "Tap a result to receive the PDF."
)


# ---------- PROFILE ----------

PROFILE_HEADER = (
    "👤 *Your Profile*\n\n"
)

PROFILE_STATS = (
    "📄 PDFs uploaded: {count}\n"
    "📅 Member since: {date}"
)

PROFILE_NO_UPLOADS = (
    "📭 You haven't uploaded any PDFs yet."
)