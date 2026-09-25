# doctors_enricher.py

DOCTORS_EXTRA_INFO = {
    "Белогурова Алена Вячеславовна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/219141/2486688-219141-belogurova_square.jpg", 
        "experience": "15 лет, к.м.н.",
        "description": "Кандидат медицинских наук, врач-офтальмолог, лазерный и рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/new/rate/doctor/219141/",
        "branches": ["Профсоюзная"]
    },
    "Белогурова Алёна Вячеславовна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/219141/2486688-219141-belogurova_square.jpg", 
        "experience": "15 лет, к.м.н.",
        "description": "Кандидат медицинских наук, врач-офтальмолог, лазерный и рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/new/rate/doctor/219141/",
        "branches": ["Профсоюзная"]
    },
    "Малахова Алена Валерьевна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/506706/887814-506706-malahova_square.jpg",
        "experience": "10 лет",
        "description": "Врач-офтальмолог, лазерный и рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/new/rate/doctor/506706/",
        "branches": ["Профсоюзная"]
    },
    "Турыгина Наталия Анатольевна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/447329/3210533-447329-turygina_square.jpg",
        "experience": "10 лет",
        "description": "Врач-офтальмолог, рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/new/rate/doctor/447329/",
        "branches": ["Профсоюзная"]
    },
    "Турыгина Наталья Анатольевна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/447329/3210533-447329-turygina_square.jpg",
        "experience": "10 лет",
        "description": "Врач-офтальмолог, рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/new/rate/doctor/447329/",
        "branches": ["Профсоюзная"]
    },
    "Гуртовая Алена Викторовна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/927221/4322291-927221-gurtovaya_square.jpg",
        "experience": "6 лет",
        "description": "Врач-офтальмолог, рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/927221-gurtovaya/",
        "branches": ["Профсоюзная", "Ватутинки"]
    },
    "Гуртовая Алёна Викторовна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/927221/4322291-927221-gurtovaya_square.jpg",
        "experience": "6 лет",
        "description": "Врач-офтальмолог, рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/927221-gurtovaya/",
        "branches": ["Профсоюзная", "Ватутинки"]
    },
    "Бегизова Фатима Владимировна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/219371/1051843-219371-begizova_square.jpg",
        "experience": "22 года",
        "description": "Врач-офтальмолог, детский офтальмолог(от 7 лет)",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/219371-begizova/",
        "branches": ["Ватутинки"]
    },
    "Тарелкина Юлия Леонидовна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/445297/3301106-445297-tarelkina_square.jpg",
        "experience": "13 лет",
        "description": "Врач-офтальмолог, рефракционный хирург, детский офтальмолог(от 0 лет) ",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/445297-tarelkina/",
        "branches": ["Профсоюзная"]
    },
    "Давтян Карина Кареновна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/703301/2590757-703301-davtyan_square.jpg",
        "experience": "12 лет, к.м.н.",
        "description": "Врач-офтальмолог, рефракционный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/703301-davtyan/",
        "branches": ["Профсоюзная"]
    },
    "Луговской Артём Евгеньевич": {
        "photo_url": "https://prodoctorov.ru/media/photo/samara/doctorimage/1011062/1765630-1011062-lugovskoy_square.jpg",
        "experience": "11 лет",
        "description": "Врач-офтальмолог, рефракционный хирург, катаркатальный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/1287452-lugovskoy/",
        "branches": ["Профсоюзная", "Ватутинки"]
    },
    "Луговской Артем Евгеньевич": {
        "photo_url": "https://prodoctorov.ru/media/photo/samara/doctorimage/1011062/1765630-1011062-lugovskoy_square.jpg",
        "experience": "11 лет",
        "description": "Врач-офтальмолог, рефракционный хирург, катаркатальный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/1287452-lugovskoy/",
        "branches": ["Профсоюзная", "Ватутинки"]
    },
    "Гветадзе Анна Анзоровна": {
        "photo_url": "https://prodoctorov.ru/media/photo/moskva/doctorimage/457472/820655-457472-gvetadze_square.jpg",
        "experience": "17 лет, к.м.н.",
        "description": "Врач-офтальмолог, лазерный хирург",
        "prodoctorov_url": "https://prodoctorov.ru/moskva/vrach/457472-gvetadze/",
        "branches": ["Профсоюзная"]
    }
}

def enrich_doctors_data(doctors_from_1c: list, target_branch: str = None) -> list:
    enriched_list = []
    for doc in doctors_from_1c:
        doc_dict = dict(doc) if not isinstance(doc, dict) else doc.copy()
        name = doc_dict.get("full_name", "").strip()
        
        found_info = None
        for key in DOCTORS_EXTRA_INFO:
            if key.replace("ё", "е").lower() in name.replace("ё", "е").lower():
                found_info = DOCTORS_EXTRA_INFO[key]
                break
                
        # --- ФИЛЬТРАЦИЯ ПО ФИЛИАЛУ ---
        if target_branch and found_info:
            doctor_branches = found_info.get("branches", [])
            if doctor_branches and target_branch not in doctor_branches:
                continue

        if found_info:
            doc_dict["photo_url"] = found_info["photo_url"]
            doc_dict["experience"] = found_info["experience"]
            doc_dict["description"] = found_info["description"]
            doc_dict["prodoctorov_url"] = found_info.get("prodoctorov_url", "")
        else:
            doc_dict["photo_url"] = "" 
            doc_dict["experience"] = "от 5 лет"
            doc_dict["description"] = "Высококвалифицированный специалист клиники «ЯСНО ВИЖУ»."
            doc_dict["prodoctorov_url"] = ""
            
        enriched_list.append(doc_dict)
        
    return enriched_list