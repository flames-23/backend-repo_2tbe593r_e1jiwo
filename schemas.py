"""
Database Schemas for the matchmaking app

Each Pydantic model maps to a MongoDB collection (lowercased class name).
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import date

Religion = Literal[
    "Islam", "Katolik", "Protestan", "Hindu", "Budha", "Khonghucu", "Agnostik", "Lainnya"
]
Religiosity = Literal["tidak menjalankan", "moderat", "strict"]
MaritalStatus = Literal["lajang", "duda", "janda"]
YesNo = Literal["ya", "tidak"]
LifestyleSmoking = Literal["tidak", "kadang", "sering"]
LifestyleAlcohol = Literal["tidak", "sosial", "sering"]
Diet = Literal["bebas", "vegetarian", "vegan", "halal", "lainnya"]
PhysicalActivity = Literal["rendah", "sedang", "tinggi"]
SleepHabit = Literal["malam", "pagi", "fleksibel"]
TimeManagement = Literal["terencana", "spontan", "campuran"]
ShoppingHabit = Literal["hemat", "moderat", "boros"]

class Lifestyle(BaseModel):
    merokok: LifestyleSmoking = Field(default="tidak")
    alkohol: LifestyleAlcohol = Field(default="tidak")
    pola_makan: Diet = Field(default="bebas")
    aktivitas_fisik: PhysicalActivity = Field(default="sedang")
    kebiasaan_tidur: SleepHabit = Field(default="fleksibel")
    pengelolaan_waktu: TimeManagement = Field(default="campuran")
    kebiasaan_belanja: ShoppingHabit = Field(default="moderat")

class SocialLinks(BaseModel):
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    tiktok: Optional[str] = None

class User(BaseModel):
    email: str = Field(..., description="Email (used only for login/payment record)")
    name: str
    tanggal_lahir: date
    status: MaritalStatus
    agama: Religion
    level_agama: Religiosity
    suku: Optional[str] = None
    hobi: List[str] = Field(default_factory=list)
    tinggi_cm: Optional[int] = Field(default=None, ge=50, le=250)
    berat_kg: Optional[int] = Field(default=None, ge=20, le=300)
    berkacamata: Optional[bool] = None
    alamat_asli: Optional[str] = None
    alamat_domisili: Optional[str] = None
    jumlah_saudara: Optional[int] = Field(default=None, ge=0, le=20)
    kondisi_keluarga: Optional[str] = None
    riwayat_penyakit: Optional[str] = None
    pekerjaan: Optional[str] = None
    usaha_sampingan: Optional[str] = None
    pendapatan_per_bulan: Optional[int] = Field(default=None, ge=0)
    pendidikan: Optional[str] = None
    bahasa: List[str] = Field(default_factory=list)
    rencana_anak: Optional[str] = None
    love_language: Optional[str] = None
    lifestyle: Lifestyle = Field(default_factory=Lifestyle)
    social: SocialLinks = Field(default_factory=SocialLinks)
    kota: Optional[str] = None
    foto_url: Optional[str] = None
    verified: bool = False
    approved: bool = False
    liked_user_ids: List[str] = Field(default_factory=list)
    matches: List[str] = Field(default_factory=list)

class Like(BaseModel):
    from_user_id: str
    to_user_id: str

class Message(BaseModel):
    match_id: str
    sender_id: str
    text: str

class AdminAction(BaseModel):
    user_id: str
    action: Literal["approve", "reject", "verify", "unverify"]

class SearchQuery(BaseModel):
    usia_min: Optional[int] = None
    usia_max: Optional[int] = None
    lokasi: Optional[str] = None
    agama: Optional[Religion] = None
    level_agama: Optional[Religiosity] = None
    pekerjaan: Optional[str] = None
    pendapatan_min: Optional[int] = None
    pendidikan: Optional[str] = None
    lifestyle: Optional[Lifestyle] = None
