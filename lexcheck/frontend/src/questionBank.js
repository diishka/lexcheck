const assistantQuestionsRu = [
  "Мы открываем ООО. Что стоит проверить в базе перед регистрацией?",
  "Компания закрывается. Что посмотреть по ликвидации и уведомлению кредиторов?",
  "Несовершеннолетний хочет сам подписать договор. Какие нормы и статьи нам важны?",
  "Опекун собирается продать имущество подопечного. Что нужно проверить заранее?",
  "Хочу выдать представителю доверенность на сделку. Что из базы посмотреть сначала?",
  "Учредители меняют устав и состав участников. Какие документы и статьи стоит проверить?",
  "Нужно оформить опеку над гражданином. Какие нормы и статьи посмотреть в первую очередь?",
  "Гражданина хотят признать ограниченно дееспособным. Какие нормы и статьи нужно проверить?",
  "Нужно зарегистрировать акт гражданского состояния. Какие документы и статьи нам нужны?",
  "Несовершеннолетний собирается распорядиться своим имуществом. Какие нормы стоит посмотреть?",
  "Компания хочет провести реорганизацию. Какие документы и статьи проверить заранее?",
  "Перед подготовкой гражданско-правового договора хочу понять базовые принципы. Что посмотреть в базе?",
  "Нужно определить полномочия представителя по доверенности. Какие нормы и статьи важны?",
  "Участник выходит из юридического лица. Какие документы и статьи стоит проверить?",
  "Хотим оформить сделку через представителя. Что обязательно проверить по базе до подписания?",
  /*
  Архив русских вопросов:
  "Какие документы в базе регулируют регистрацию юридических лиц?",
  "Какие нормы относятся к реорганизации юридических лиц?",
  "Какие статьи связаны с ликвидацией юридических лиц?",
  "Какие документы регулируют деятельность обществ с ограниченной ответственностью?",
  "Какие нормы относятся к коммерческим организациям?",
  "Покажи статьи по банкротству и санации юридических лиц.",
  "Какие нормы в базе связаны с опекой и попечительством?",
  "Какие статьи касаются ограничения дееспособности граждан?",
  "Какие документы относятся к правовому положению несовершеннолетних?",
  "Какие нормы регулируют регистрацию актов гражданского состояния?",
  "Какие статьи в базе связаны с предпринимательской деятельностью граждан?",
  "Какие документы регулируют товарный знак и знак обслуживания?",
  "Какие нормы касаются фирменного наименования юридического лица?",
  "Какие статьи связаны с правами потребителей при дистанционной продаже?",
  "Какие документы регулируют электронную торговлю в Узбекистане?",
  "Какие нормы относятся к защите персональных данных?",
  "Какие статьи связаны с рекламой финансовых услуг?",
  "Какие документы регулируют банковскую деятельность?",
  "Какие нормы касаются лицензирования отдельных видов деятельности?",
  "Какие статьи связаны с налогообложением электронной коммерции?",
  "Какие нормы регулируют трудовой договор и его прекращение?",
  "Какие статьи касаются удаленной работы и платформенной занятости?",
  "Какие документы регулируют охрану интеллектуальной собственности?",
  "Какие нормы относятся к авторским правам на программное обеспечение?",
  "Какие статьи регулируют договор аренды нежилого помещения?",
  "Какие нормы связаны с доверенностью и представительством?",
  "Какие документы регулируют сделки, требующие нотариального удостоверения?",
  "Какие статьи относятся к наследованию по закону и по завещанию?",
  "Какие нормы в базе касаются брачного договора?",
  "Какие документы регулируют алиментные обязательства?",
  "Какие статьи относятся к праву собственности на земельный участок?",
  "Какие нормы регулируют строительство и ввод объектов в эксплуатацию?",
  "Какие документы касаются экологических требований к предприятиям?",
  "Какие статьи регулируют фармацевтическую деятельность и оборот лекарств?",
  "Какие нормы связаны с медицинской лицензией частной клиники?",
  "Какие документы регулируют деятельность образовательных учреждений?",
  "Какие статьи касаются государственной аккредитации учебных организаций?",
  "Какие нормы относятся к государственным закупкам и обжалованию результатов?",
  "Какие документы регулируют валютные операции и переводы за рубеж?",
  "Какие статьи связаны с таможенным оформлением временного ввоза?",
  "Какие нормы в базе касаются внешнеэкономической деятельности?",
  "Какие документы регулируют защиту деловой репутации юридического лица?",
  "Какие статьи относятся к недобросовестной конкуренции?",
  "Какие нормы регулируют раскрытие информации в рекламе и оферте?",
  "Какие документы касаются прав иностранцев на трудовую деятельность?",
  "Какие статьи регулируют аренду государственного имущества?",
  "Какие нормы относятся к публично-частному партнерству?",
  "Какие документы регулируют деятельность микрофинансовых организаций?",
  "Какие статьи касаются электронного документооборота и электронной подписи?",
  "Какие нормы связаны с хранением и трансграничной передачей данных?",
  "Какие документы регулируют создание филиалов и представительств?",
  "Какие статьи относятся к общим положениям гражданского права?",
  "Какие нормы регулируют порядок внесения изменений в учредительные документы?",
  "Какие документы в базе связаны с УП-110?",
  "Покажи точные статьи по регистрации, реорганизации и ликвидации юридических лиц.",
  */
]

const analyzerExamplesRu = [
  {
    id: "registration_without_address",
    title: "Стартап хочет зарегистрировать юрлицо без адреса и проверки документов",
    text: "Юридическое лицо может быть зарегистрировано без указания юридического адреса, без сведений об учредителях и без обязательной проверки достоверности представленных документов.",
  },
  {
    id: "liquidation_without_creditors",
    title: "Компания хочет ликвидироваться без уведомления кредиторов",
    text: "Организация может быть ликвидирована по заявлению одного участника без уведомления кредиторов и без публикации сведений о ликвидации.",
  },
  {
    id: "minor_any_transactions",
    title: "Предлагается разрешить несовершеннолетним любые сделки без согласия родителей",
    text: "Граждане, достигшие 14 лет, вправе без согласия родителей заключать любые сделки, брать кредиты и отчуждать имущество.",
  },
  {
    id: "guardian_sell_without_permission",
    title: "Опекун хочет продать имущество подопечного без разрешения органа",
    text: "Законный представитель вправе продавать имущество подопечного без предварительного разрешения уполномоченного органа.",
  },
  {
    id: "representative_without_power",
    title: "Компания хочет дать представителю право на любые сделки без письменной доверенности",
    text: "Представитель вправе совершать любые сделки от имени доверителя без письменной доверенности и без ограничения по сумме сделки.",
  },
  /*
  Архив русских кейсов анализатора:
  - Законопроект о регистрации компаний без адреса
  - Законопроект об упрощенной ликвидации ООО
  - Законопроект о браке без государственной регистрации
  - Законопроект об ограничении дееспособности без суда
  - Законопроект о назначении опекуна без согласия семьи
  - Законопроект о распоряжении имуществом подопечного
  - Законопроект о продаже недвижимости несовершеннолетних
  - Законопроект о полной дееспособности с 14 лет
  - Законопроект о продаже криптовалют без лицензии
  - Законопроект о рекламе финансовых услуг без раскрытия рисков
  - Законопроект о сборе персональных данных без согласия
  - Законопроект о трансграничной передаче данных без ограничений
  - Законопроект об отказе в выдаче сведений потребителю
  - Законопроект о невозврате денег при дистанционной продаже
  - Законопроект о бессрочном испытательном сроке
  - Законопроект о неоплачиваемой платформенной занятости
  - Законопроект о запрете больничных выплат
  - Законопроект о полной свободе сверхурочной работы
  - Законопроект о запрете профсоюзов в частных компаниях
  - Законопроект об одностороннем расторжении брака без уведомления
  - Законопроект об отказе в алиментах на ребенка
  - Законопроект о свободной продаже лекарств
  - Законопроект о деятельности частных клиник без лицензии
  - Законопроект о рекламе лекарств без ограничений
  - Законопроект об открытии школы без аккредитации
  - Законопроект о закрытом доступе к образованию
  - Законопроект о валютных переводах без контроля
  - Законопроект о банковских услугах без лицензии
  - Законопроект о микрозаймах без лимитов
  - Законопроект о блокировке счетов без решения суда
  - Законопроект о приватизации земли без аукциона
  - Законопроект о строительстве без разрешения
  - Законопроект о вводе объекта без проверки безопасности
  - Законопроект об отказе от экологической экспертизы
  - Законопроект о выбросах без отчетности
  - Законопроект о свободном использовании товарных знаков
  - Законопроект об отказе от охраны авторских прав на софт
  - Законопроект о принудительной передаче исходного кода
  - Законопроект о госзакупках без конкурса
  - Законопроект о запрете обжалования закупки
  - Законопроект о таможенном ввозе без декларирования
  - Законопроект о ввозе лекарств без сертификации
  - Законопроект о деятельности филиала без регистрации
  - Законопроект о свободной передаче доли в ООО
  - Законопроект о необязательности устава
  - Законопроект о смене директора без решения участников
  - Законопроект о полной конфиденциальности бенефициаров
  - Законопроект о рекламе, ориентированной на детей
  - Законопроект о недобросовестном сравнении конкурентов
  - Законопроект о полной свободе оферты на маркетплейсе
  - Законопроект о хранении данных пользователей бессрочно
  - Законопроект об электронной подписи без идентификации
  - Законопроект об иностранной трудовой деятельности без разрешения
  - Законопроект об аренде госимущества без оценки
  */
]

const assistantQuestionsUz = [
  "Biz MChJ ochmoqchimiz. Ro'yxatdan o'tkazishdan oldin bazadan nimani tekshirish kerak?",
  "Tashkilotni tugatmoqchimiz. Kreditorlarni xabardor qilish bo'yicha nimani ko'rish kerak?",
  "Voyaga yetmagan shaxs shartnomani o'zi imzolamoqchi. Qaysi normalar biz uchun muhim?",
  "Vasiy mol-mulkni sotmoqchi. Oldindan qaysi hujjat va moddalarni tekshirish kerak?",
  "Vakilga bitim tuzish vakolatini bermoqchiman. Avval bazadan nimani ko'rish kerak?",
  "Ta'sischilar ustav va ishtirokchilar tarkibini o'zgartirmoqchi. Qaysi hujjat va moddalarni tekshirish kerak?",
  "Fuqaroga vasiylik rasmiylashtirmoqchimiz. Avvalo qaysi normalar va moddalarni ko'rish kerak?",
  "Fuqaroni muomala layoqati cheklangan deb topishmoqchi. Qaysi normalar va moddalarni tekshirish kerak?",
  "Fuqarolik holati dalolatnomasini ro'yxatdan o'tkazish kerak. Qaysi hujjat va moddalar kerak bo'ladi?",
  "Voyaga yetmagan shaxs o'z mol-mulkini tasarruf etmoqchi. Qaysi normalarni ko'rish kerak?",
  "Kompaniya qayta tashkil etilmoqchi. Qaysi hujjat va moddalarni oldindan tekshirish kerak?",
  "Fuqarolik-huquqiy shartnoma tayyorlashdan oldin asosiy tamoyillarni bilmoqchiman. Bazadan nimani ko'ray?",
  "Ishonchnoma bo'yicha vakilning vakolatlarini aniqlash kerak. Qaysi normalar va moddalar muhim?",
  "Ishtirokchi yuridik shaxs tarkibidan chiqmoqchi. Qaysi hujjat va moddalarni tekshirish kerak?",
  "Bitimni vakil orqali rasmiylashtirmoqchimiz. Imzolashdan oldin bazadan nimani albatta tekshirish kerak?",
  /*
  Arxivdagi o'zbekcha savollar:
  "Bazadagi qaysi hujjatlar yuridik shaxslarni ro'yxatdan o'tkazishni tartibga soladi?",
  "Qaysi normalar yuridik shaxslarni qayta tashkil etishga taalluqli?",
  "Qaysi moddalar yuridik shaxslarni tugatish bilan bog'liq?",
  "Qaysi hujjatlar mas'uliyati cheklangan jamiyatlar faoliyatini tartibga soladi?",
  "Qaysi normalar tijorat tashkilotlariga taalluqli?",
  "Yuridik shaxslarning bankrotligi va sanatsiyasi bo'yicha moddalarni ko'rsat.",
  "Bazadagi qaysi normalar vasiylik va homiylik bilan bog'liq?",
  "Qaysi moddalar fuqarolarning muomala layoqatini cheklashga taalluqli?",
  "Qaysi hujjatlar voyaga yetmaganlarning huquqiy maqomiga taalluqli?",
  "Qaysi normalar fuqarolik holati dalolatnomalarini ro'yxatdan o'tkazishni tartibga soladi?",
  "Bazadagi qaysi moddalar fuqarolarning tadbirkorlik faoliyati bilan bog'liq?",
  "Qaysi hujjatlar tovar belgisi va xizmat ko'rsatish belgisini tartibga soladi?",
  "Qaysi normalar yuridik shaxsning firma nomiga taalluqli?",
  "Qaysi moddalar masofaviy savdoda iste'molchilarning huquqlari bilan bog'liq?",
  "Qaysi hujjatlar O'zbekistonda elektron savdoni tartibga soladi?",
  "Qaysi normalar shaxsga doir ma'lumotlarni himoya qilishga taalluqli?",
  "Qaysi moddalar moliyaviy xizmatlar reklamasi bilan bog'liq?",
  "Qaysi hujjatlar bank faoliyatini tartibga soladi?",
  "Qaysi normalar ayrim faoliyat turlarini litsenziyalashga taalluqli?",
  "Qaysi moddalar elektron tijoratni soliqqa tortish bilan bog'liq?",
  "Qaysi normalar mehnat shartnomasi va uni bekor qilishni tartibga soladi?",
  "Qaysi moddalar masofaviy ish va platforma bandligiga taalluqli?",
  "Qaysi hujjatlar intellektual mulkni himoya qilishni tartibga soladi?",
  "Qaysi normalar dasturiy ta'minotga mualliflik huquqlariga taalluqli?",
  "Qaysi moddalar noturar joy ijara shartnomasini tartibga soladi?",
  "Qaysi normalar ishonchnoma va vakillik bilan bog'liq?",
  "Qaysi hujjatlar notarial tasdiqlashni talab qiladigan bitimlarni tartibga soladi?",
  "Qaysi moddalar qonun bo'yicha va vasiyat bo'yicha merosga taalluqli?",
  "Bazadagi qaysi normalar nikoh shartnomasiga taalluqli?",
  "Qaysi hujjatlar aliment majburiyatlarini tartibga soladi?",
  "Qaysi moddalar yer uchastkasiga mulk huquqiga taalluqli?",
  "Qaysi normalar qurilish va obyektlarni foydalanishga topshirishni tartibga soladi?",
  "Qaysi hujjatlar korxonalarga qo'yiladigan ekologik talablarga taalluqli?",
  "Qaysi moddalar farmatsevtika faoliyati va dori vositalari muomalasini tartibga soladi?",
  "Qaysi normalar xususiy klinikaning tibbiy litsenziyasi bilan bog'liq?",
  "Qaysi hujjatlar ta'lim muassasalari faoliyatini tartibga soladi?",
  "Qaysi moddalar ta'lim tashkilotlarining davlat akkreditatsiyasiga taalluqli?",
  "Qaysi normalar davlat xaridlari va natijalarni shikoyat qilishga taalluqli?",
  "Qaysi hujjatlar valyuta operatsiyalari va chet elga o'tkazmalarni tartibga soladi?",
  "Qaysi moddalar vaqtincha olib kirishning bojxona rasmiylashtiruvi bilan bog'liq?",
  "Bazadagi qaysi normalar tashqi iqtisodiy faoliyatga taalluqli?",
  "Qaysi hujjatlar yuridik shaxsning ishbilarmonlik obro'sini himoya qilishni tartibga soladi?",
  "Qaysi moddalar g'irrom raqobatga taalluqli?",
  "Qaysi normalar reklama va ofertada ma'lumotlarni oshkor qilishni tartibga soladi?",
  "Qaysi hujjatlar chet elliklarning mehnat faoliyati huquqlariga taalluqli?",
  "Qaysi moddalar davlat mulkini ijaraga berishni tartibga soladi?",
  "Qaysi normalar davlat-xususiy sheriklikka taalluqli?",
  "Qaysi hujjatlar mikromoliya tashkilotlari faoliyatini tartibga soladi?",
  "Qaysi moddalar elektron hujjat aylanishi va elektron imzoga taalluqli?",
  "Qaysi normalar ma'lumotlarni saqlash va transchegaraviy uzatish bilan bog'liq?",
  "Qaysi hujjatlar filial va vakolatxonalar tashkil etilishini tartibga soladi?",
  "Qaysi moddalar fuqarolik huquqining umumiy qoidalariga taalluqli?",
  "Qaysi normalar ta'sis hujjatlariga o'zgartirish kiritish tartibini tartibga soladi?",
  "Bazadagi qaysi hujjatlar UP-110 bilan bog'liq?",
  "Yuridik shaxslarni ro'yxatdan o'tkazish, qayta tashkil etish va tugatish bo'yicha aniq moddalarni ko'rsat.",
  */
]

const analyzerExamplesUz = [
  {
    id: "registration_without_address",
    title: "Startap yuridik shaxsni manzilsiz va tekshiruvsiz ro'yxatdan o'tkazmoqchi",
    text: "Yuridik shaxs yuridik manzili ko'rsatilmasdan, ta'sischilar to'g'risidagi ma'lumotlarsiz va taqdim etilgan hujjatlarning ishonchliligini majburiy tekshirmasdan ro'yxatdan o'tkazilishi mumkin.",
  },
  {
    id: "liquidation_without_creditors",
    title: "Kompaniya kreditorlarni ogohlantirmasdan tugatilmoqchi",
    text: "Tashkilot kreditorlarni xabardor qilmasdan va tugatish to'g'risidagi ma'lumotlarni e'lon qilmasdan bitta ishtirokchining arizasi asosida tugatilishi mumkin.",
  },
  {
    id: "minor_any_transactions",
    title: "Voyaga yetmaganlarga ota-ona roziligisiz har qanday bitimga ruxsat berilmoqda",
    text: "14 yoshga to'lgan fuqarolar ota-onasining roziligisiz har qanday bitimlarni tuzish, kredit olish va mol-mulkni begonalashtirishga haqli.",
  },
  {
    id: "guardian_sell_without_permission",
    title: "Vasiylik ostidagi shaxs mol-mulki ruxsatsiz sotilmoqchi",
    text: "Qonuniy vakil vakolatli organning oldindan ruxsatisiz vasiylik ostidagi shaxs mol-mulkini sotishga haqli.",
  },
  {
    id: "representative_without_power",
    title: "Vakilga yozma ishonchnomasiz har qanday bitim tuzish vakolati berilmoqda",
    text: "Vakil ishonchnomasiz va bitim summasi bo'yicha cheklovsiz ishonch bildiruvchining nomidan har qanday bitimlarni tuzishga haqli.",
  },
  /*
  Arxivdagi o'zbekcha analizator кейслари:
  - Kompaniyalarni manzilsiz ro'yxatdan o'tkazish haqidagi qonun loyihasi
  - MChJni soddalashtirilgan tartibda tugatish haqidagi qonun loyihasi
  - Davlat ro'yxatidan o'tkazmasdan nikoh haqidagi qonun loyihasi
  - Sudsiz muomala layoqatini cheklash haqidagi qonun loyihasi
  - Oila roziligisiz vasiy tayinlash haqidagi qonun loyihasi
  - Vasiylik ostidagi shaxs mulkini tasarruf etish haqidagi qonun loyihasi
  - Voyaga yetmaganlar ko'chmas mulkini sotish haqidagi qonun loyihasi
  - 14 yoshdan to'liq muomala layoqati haqidagi qonun loyihasi
  - Litsenziyasiz kriptovalyuta savdosi haqidagi qonun loyihasi
  - Xavflarni oshkor qilmasdan moliyaviy xizmatlarni reklama qilish haqidagi qonun loyihasi
  - Roziliksiz shaxsga doir ma'lumotlarni yig'ish haqidagi qonun loyihasi
  - Ma'lumotlarni cheklovsiz transchegaraviy uzatish haqidagi qonun loyihasi
  - Iste'molchiga ma'lumot bermaslik haqidagi qonun loyihasi
  - Masofaviy savdoda pulni qaytarmaslik haqidagi qonun loyihasi
  - Muddatsiz sinov muddati haqidagi qonun loyihasi
  - Haq to'lanmaydigan platforma bandligi haqidagi qonun loyihasi
  - Kasallik varaqasi to'lovlarini taqiqlash haqidagi qonun loyihasi
  - Qo'shimcha ishga to'liq erkin jalb qilish haqidagi qonun loyihasi
  - Xususiy kompaniyalarda kasaba uyushmalarini taqiqlash haqidagi qonun loyihasi
  - Xabarnomasiz bir tomonlama nikohni bekor qilish haqidagi qonun loyihasi
  - Bolaga aliment to'lashni rad etish haqidagi qonun loyihasi
  - Dori vositalarini erkin sotish haqidagi qonun loyihasi
  - Xususiy klinikalar faoliyatini litsenziyasiz yuritish haqidagi qonun loyihasi
  - Dori reklamasi uchun cheklovlarsiz haqidagi qonun loyihasi
  - Akkreditatsiyasiz maktab ochish haqidagi qonun loyihasi
  - Ta'limga yopiq kirish haqidagi qonun loyihasi
  - Nazoratsiz valyuta o'tkazmalari haqidagi qonun loyihasi
  - Litsenziyasiz bank xizmatlari haqidagi qonun loyihasi
  - Cheklovsiz mikrozayomlar haqidagi qonun loyihasi
  - Sud qarorisiz hisoblarni bloklash haqidagi qonun loyihasi
  - Auksionsiz yer xususiylashtirish haqidagi qonun loyihasi
  - Ruxsatsiz qurilish haqidagi qonun loyihasi
  - Xavfsizlik tekshiruvisiz obyektni foydalanishga topshirish haqidagi qonun loyihasi
  - Ekologik ekspertizadan voz kechish haqidagi qonun loyihasi
  - Hisobotsiz chiqindilar haqidagi qonun loyihasi
  - Tovar belgilaridan erkin foydalanish haqidagi qonun loyihasi
  - Dasturiy ta'minotga mualliflik huquqi himoyasidan voz kechish haqidagi qonun loyihasi
  - Boshlang'ich kodni majburiy topshirish haqidagi qonun loyihasi
  - Tanlovsiz davlat xaridlari haqidagi qonun loyihasi
  - Davlat xaridini shikoyat qilishni taqiqlash haqidagi qonun loyihasi
  - Deklaratsiyasiz bojxona olib kirish haqidagi qonun loyihasi
  - Dori vositalarini sertifikatsiyasiz olib kirish haqidagi qonun loyihasi
  - Filialni ro'yxatdan o'tkazmasdan faoliyat yuritish haqidagi qonun loyihasi
  - MChJ ulushini erkin o'tkazish haqidagi qonun loyihasi
  - Ustav majburiy emasligi haqidagi qonun loyihasi
  - Ishtirokchilar qarorisiz direktorni almashtirish haqidagi qonun loyihasi
  - Benefisiarlar to'liq maxfiyligi haqidagi qonun loyihasi
  - Bolalarga yo'naltirilgan reklama haqidagi qonun loyihasi
  - Raqobatchilarni g'irrom taqqoslash haqidagi qonun loyihasi
  - Marketpleys ofertasining to'liq erkinligi haqidagi qonun loyihasi
  - Foydalanuvchi ma'lumotlarini muddatsiz saqlash haqidagi qonun loyihasi
  - Identifikatsiyasiz elektron imzo haqidagi qonun loyihasi
  - Ruxsatsiz chet elliklarning mehnat faoliyati haqidagi qonun loyihasi
  - Baholashsiz davlat mulkini ijaraga berish haqidagi qonun loyihasi
  */
]

export const QUESTION_BANK = {
  ru: {
    assistant: assistantQuestionsRu,
    analyzer: analyzerExamplesRu,
  },
  uz: {
    assistant: assistantQuestionsUz,
    analyzer: analyzerExamplesUz,
  },
}

export function getAssistantQuestions(lang = 'ru') {
  return QUESTION_BANK[lang]?.assistant || QUESTION_BANK.ru.assistant
}

export function getAnalyzerExamples(lang = 'ru') {
  return QUESTION_BANK[lang]?.analyzer || QUESTION_BANK.ru.analyzer
}

export function pickRandomItems(items, count = 5) {
  const copy = Array.isArray(items) ? [...items] : []
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy.slice(0, Math.max(0, count))
}
