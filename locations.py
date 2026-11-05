"""Philippine locations used by the Create / Edit Project dropdown.

Grouped by region so the <select> can render <optgroup>s. Each value is saved
to Project.location exactly as written ("City, Province/Area").
"""

PH_LOCATIONS = {
    "National Capital Region (Metro Manila)": [
        "Caloocan City, Metro Manila", "Las Piñas City, Metro Manila", "Makati City, Metro Manila",
        "Malabon City, Metro Manila", "Mandaluyong City, Metro Manila", "Manila City, Metro Manila",
        "Marikina City, Metro Manila", "Muntinlupa City, Metro Manila", "Navotas City, Metro Manila",
        "Parañaque City, Metro Manila", "Pasay City, Metro Manila", "Pasig City, Metro Manila",
        "Pateros, Metro Manila", "Quezon City, Metro Manila", "San Juan City, Metro Manila",
        "Taguig City, Metro Manila", "Valenzuela City, Metro Manila",
    ],
    "Cordillera Administrative Region": [
        "Baguio City, Benguet", "La Trinidad, Benguet", "Tabuk City, Kalinga",
    ],
    "Ilocos Region": [
        "Laoag City, Ilocos Norte", "Batac City, Ilocos Norte", "Vigan City, Ilocos Sur",
        "Candon City, Ilocos Sur", "San Fernando City, La Union", "Alaminos City, Pangasinan",
        "Dagupan City, Pangasinan", "San Carlos City, Pangasinan", "Urdaneta City, Pangasinan",
    ],
    "Cagayan Valley": [
        "Tuguegarao City, Cagayan", "Ilagan City, Isabela", "Cauayan City, Isabela",
        "Santiago City, Isabela", "Bayombong, Nueva Vizcaya",
    ],
    "Central Luzon": [
        "Balanga City, Bataan", "Malolos City, Bulacan", "Meycauayan City, Bulacan",
        "San Jose del Monte City, Bulacan", "Cabanatuan City, Nueva Ecija", "Gapan City, Nueva Ecija",
        "Palayan City, Nueva Ecija", "San Jose City, Nueva Ecija", "Angeles City, Pampanga",
        "Mabalacat City, Pampanga", "San Fernando City, Pampanga", "Tarlac City, Tarlac",
        "Olongapo City, Zambales", "Iba, Zambales",
    ],
    "CALABARZON": [
        "Batangas City, Batangas", "Lipa City, Batangas", "Tanauan City, Batangas",
        "Bacoor City, Cavite", "Cavite City, Cavite", "Dasmariñas City, Cavite",
        "General Trias City, Cavite", "Imus City, Cavite", "Tagaytay City, Cavite",
        "Trece Martires City, Cavite", "Biñan City, Laguna", "Calamba City, Laguna",
        "San Pablo City, Laguna", "San Pedro City, Laguna", "Santa Rosa City, Laguna",
        "Lucena City, Quezon", "Tayabas City, Quezon", "Antipolo City, Rizal",
        "Cainta, Rizal", "Taytay, Rizal",
    ],
    "MIMAROPA": [
        "Calapan City, Oriental Mindoro", "San Jose, Occidental Mindoro",
        "Puerto Princesa City, Palawan", "Romblon, Romblon",
    ],
    "Bicol Region": [
        "Legazpi City, Albay", "Ligao City, Albay", "Tabaco City, Albay", "Naga City, Camarines Sur",
        "Iriga City, Camarines Sur", "Sorsogon City, Sorsogon", "Masbate City, Masbate",
        "Daet, Camarines Norte", "Virac, Catanduanes",
    ],
    "Western Visayas": [
        "Roxas City, Capiz", "Iloilo City, Iloilo", "Passi City, Iloilo", "Bacolod City, Negros Occidental",
        "Bago City, Negros Occidental", "Kabankalan City, Negros Occidental", "Silay City, Negros Occidental",
        "Kalibo, Aklan", "Boracay (Malay), Aklan", "San Jose de Buenavista, Antique", "Jordan, Guimaras",
    ],
    "Central Visayas": [
        "Tagbilaran City, Bohol", "Bogo City, Cebu", "Carcar City, Cebu", "Cebu City, Cebu",
        "Danao City, Cebu", "Lapu-Lapu City, Cebu", "Mandaue City, Cebu", "Talisay City, Cebu",
        "Toledo City, Cebu", "Dumaguete City, Negros Oriental", "Bais City, Negros Oriental",
        "Siquijor, Siquijor",
    ],
    "Eastern Visayas": [
        "Tacloban City, Leyte", "Ormoc City, Leyte", "Baybay City, Leyte", "Catbalogan City, Samar",
        "Calbayog City, Samar", "Borongan City, Eastern Samar", "Maasin City, Southern Leyte",
        "Naval, Biliran",
    ],
    "Zamboanga Peninsula": [
        "Zamboanga City, Zamboanga del Sur", "Pagadian City, Zamboanga del Sur",
        "Dipolog City, Zamboanga del Norte", "Dapitan City, Zamboanga del Norte",
        "Isabela City, Basilan",
    ],
    "Northern Mindanao": [
        "Cagayan de Oro City, Misamis Oriental", "El Salvador City, Misamis Oriental",
        "Gingoog City, Misamis Oriental", "Iligan City, Lanao del Norte", "Oroquieta City, Misamis Occidental",
        "Ozamiz City, Misamis Occidental", "Tangub City, Misamis Occidental", "Malaybalay City, Bukidnon",
        "Valencia City, Bukidnon", "Mambajao, Camiguin",
    ],
    "Davao Region": [
        "Davao City, Davao del Sur", "Digos City, Davao del Sur", "Panabo City, Davao del Norte",
        "Tagum City, Davao del Norte", "Island Garden City of Samal, Davao del Norte", "Mati City, Davao Oriental",
    ],
    "SOCCSKSARGEN": [
        "General Santos City, South Cotabato", "Koronadal City, South Cotabato", "Kidapawan City, Cotabato",
        "Tacurong City, Sultan Kudarat",
    ],
    "Caraga": [
        "Butuan City, Agusan del Norte", "Cabadbaran City, Agusan del Norte", "Bayugan City, Agusan del Sur",
        "Surigao City, Surigao del Norte", "Bislig City, Surigao del Sur", "Tandag City, Surigao del Sur",
    ],
    "BARMM": [
        "Cotabato City, Maguindanao", "Marawi City, Lanao del Sur", "Lamitan City, Basilan",
    ],
}

# Flat set for fast server-side validation.
PH_LOCATION_VALUES = {loc for group in PH_LOCATIONS.values() for loc in group}
