-- LexCheck UZ - Database Schema
-- Run: psql -U postgres -d lexcheck -f schema.sql

CREATE EXTENSION IF NOT EXISTS unaccent;

-- Drop existing tables
DROP TABLE IF EXISTS law_articles CASCADE;
DROP TABLE IF EXISTS laws CASCADE;
DROP TABLE IF EXISTS chat_sessions CASCADE;
DROP TABLE IF EXISTS chat_messages CASCADE;

-- Laws table
CREATE TABLE laws (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(20) UNIQUE NOT NULL,
    title_ru    TEXT NOT NULL,
    title_uz    TEXT NOT NULL,
    category    VARCHAR(100) NOT NULL,
    year        INTEGER NOT NULL,
    summary_ru  TEXT,
    summary_uz  TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Law articles table
CREATE TABLE law_articles (
    id          SERIAL PRIMARY KEY,
    law_id      INTEGER REFERENCES laws(id) ON DELETE CASCADE,
    article_num VARCHAR(30) NOT NULL,
    content_ru  TEXT NOT NULL,
    content_uz  TEXT,
    keywords    TEXT[],
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Full text search indexes
-- Russian fields: use 'russian' config for proper stemming (реклам* matches реклама/рекламе/etc.)
CREATE INDEX idx_laws_fts_ru ON laws USING gin(to_tsvector('russian', coalesce(title_ru,'') || ' ' || coalesce(summary_ru,'')));
CREATE INDEX idx_articles_fts_ru ON law_articles USING gin(to_tsvector('russian', content_ru));
-- Uzbek fields: use 'simple' config (no stemming, just lowercase tokenization — correct for Latin-script Uzbek)
CREATE INDEX idx_laws_fts_uz ON laws USING gin(to_tsvector('simple', coalesce(title_uz,'') || ' ' || coalesce(summary_uz,'')));
CREATE INDEX idx_articles_fts_uz ON law_articles USING gin(to_tsvector('simple', coalesce(content_uz,'')));
CREATE INDEX idx_laws_category ON laws(category);
CREATE INDEX idx_articles_law_id ON law_articles(law_id);

-- Chat sessions
CREATE TABLE chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Chat messages
CREATE TABLE chat_messages (
    id          SERIAL PRIMARY KEY,
    session_id  UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('user','assistant','system')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ─── SEED DATA ────────────────────────────────────────────────────────────────

INSERT INTO laws (code, title_ru, title_uz, category, year, summary_ru, summary_uz) VALUES
('UZB-001',
 'Закон о защите прав потребителей',
 'Iste''molchilar huquqlarini himoya qilish to''g''risidagi Qonun',
 'Consumer Rights', 1996,
 'Регулирует отношения между продавцами и потребителями, устанавливает права покупателей и обязанности продавцов при продаже товаров и оказании услуг.',
 'Sotuvchilar va iste''molchilar o''rtasidagi munosabatlarni tartibga soladi.'),

('UZB-002',
 'Закон о рекламе',
 'Reklama to''g''risidagi Qonun',
 'Advertising', 1998,
 'Устанавливает требования к рекламной деятельности, запрещает недобросовестную и вводящую в заблуждение рекламу, регулирует отдельные виды рекламы.',
 'Reklama faoliyatiga qo''yiladigan talablarni belgilaydi.'),

('UZB-003',
 'Гражданский кодекс Республики Узбекистан',
 'O''zbekiston Respublikasi Fuqarolik kodeksi',
 'Civil Law', 1996,
 'Основной кодекс, регулирующий имущественные и личные неимущественные отношения между гражданами и юридическими лицами на основе равенства, автономии воли и имущественной самостоятельности участников.',
 'Fuqarolar va yuridik shaxslar o''rtasidagi mulkiy munosabatlarni tartibga soluvchi asosiy kodeks.'),

('UZB-004',
 'Налоговый кодекс Республики Узбекистан',
 'O''zbekiston Respublikasi Soliq kodeksi',
 'Tax Law', 2007,
 'Определяет систему налогообложения, виды налогов и сборов, порядок их исчисления, уплаты, а также права и обязанности налогоплательщиков и налоговых органов.',
 'Soliq tizimini, soliq turlari va to''lovlarni, ularni hisoblash tartibini belgilaydi.'),

('UZB-005',
 'Закон о конкуренции',
 'Raqobat to''g''risidagi Qonun',
 'Competition', 2012,
 'Направлен на защиту и развитие конкуренции, предотвращение и пресечение монополистической деятельности и недобросовестной конкуренции на товарных рынках.',
 'Raqobatni himoya qilish va rivojlantirish, monopolistik faoliyatni oldini olishga qaratilgan.'),

('UZB-006',
 'Трудовой кодекс Республики Узбекистан',
 'O''zbekiston Respublikasi Mehnat kodeksi',
 'Labour Law', 1995,
 'Регулирует трудовые отношения между работниками и работодателями, устанавливает права и обязанности сторон, гарантии в области труда, занятости и социальной защиты.',
 'Xodimlar va ish beruvchilar o''rtasidagi mehnat munosabatlarini tartibga soladi.'),

('UZB-007',
 'Закон об электронной торговле',
 'Elektron tijorat to''g''risidagi Qonun',
 'Digital Commerce', 2015,
 'Регулирует правоотношения в сфере электронной коммерции, устанавливает требования к электронным сделкам, цифровым подписям и онлайн-платежам.',
 'Elektron tijorat sohasidagi huquqiy munosabatlarni tartibga soladi.'),

('UZB-008',
 'Закон о персональных данных',
 'Shaxsiy ma''lumotlar to''g''risidagi Qonun',
 'Data Protection', 2019,
 'Устанавливает правовые основы сбора, обработки, хранения и защиты персональных данных граждан, права субъектов персональных данных и обязанности операторов.',
 'Fuqarolarning shaxsiy ma''lumotlarini to''plash, qayta ishlash va himoya qilish asoslarini belgilaydi.'),

('UZB-009',
 'Закон об образовании',
 'Ta''lim to''g''risidagi Qonun',
 'Education', 1997,
 'Определяет правовые основы системы образования Республики Узбекистан, права и обязанности участников образовательного процесса, требования к образовательным учреждениям.',
 'O''zbekiston Respublikasi ta''lim tizimining huquqiy asoslarini belgilaydi.'),

('UZB-010',
 'Закон об охране окружающей среды',
 'Atrof-muhitni muhofaza qilish to''g''risidagi Qonun',
 'Environment', 1992,
 'Регулирует отношения в области охраны окружающей среды, природопользования, экологической безопасности и устойчивого развития.',
 'Atrof-muhitni muhofaza qilish sohasidagi munosabatlarni tartibga soladi.'),

('UZB-011',
 'Закон о банках и банковской деятельности',
 'Banklar va bank faoliyati to''g''risidagi Qonun',
 'Banking', 1996,
 'Регулирует порядок создания, лицензирования и деятельности банков, устанавливает требования к банковским операциям, защите вкладчиков и финансовой стабильности.',
 'Banklar tashkil etish va litsenziyalash tartibini, bank operatsiyalariga qo''yiladigan talablarni belgilaydi.'),

('UZB-012',
 'Закон о предпринимательской деятельности',
 'Tadbirkorlik faoliyati to''g''risidagi Qonun',
 'Business', 2000,
 'Устанавливает правовые основы предпринимательской деятельности, гарантии и защиту прав предпринимателей, порядок государственной регистрации субъектов предпринимательства.',
 'Tadbirkorlik faoliyatining huquqiy asoslarini va tadbirkorlar huquqlarini himoya qilish kafolatlarini belgilaydi.');

-- Articles for UZB-001 (Consumer Rights)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-001'), 'Ст. 14',
 'Потребитель имеет право на получение полной и достоверной информации о товаре или услуге, включая состав, цену, условия приобретения, до заключения договора.',
 'Iste''molchi shartnoma tuzilgunga qadar tovar yoki xizmat haqida to''liq va ishonchli ma''lumot olish huquqiga ega.',
 ARRAY['потребитель','информация','товар','услуга','договор']),
((SELECT id FROM laws WHERE code='UZB-001'), 'Ст. 18',
 'Продавец обязан заменить товар ненадлежащего качества или вернуть уплаченную сумму в течение 14 дней с момента обращения потребителя.',
 'Sotuvchi sifatsiz tovarni almashtirish yoki to''langan summani 14 kun ichida qaytarishga majbur.',
 ARRAY['замена','качество','возврат','14 дней','продавец']),
((SELECT id FROM laws WHERE code='UZB-001'), 'Ст. 22',
 'Запрещается введение потребителей в заблуждение относительно потребительских свойств, качества товара или услуги, а также скрытие существенных недостатков.',
 'Iste''molchilarni tovar yoki xizmatning iste''mol xususiyatlari bo''yicha chalg''itish taqiqlanadi.',
 ARRAY['заблуждение','качество','потребительские свойства','недостатки']);

-- Articles for UZB-002 (Advertising)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-002'), 'Ст. 5',
 'Реклама должна быть достоверной, добросовестной, не вводить потребителей в заблуждение. Недостоверная реклама запрещена.',
 'Reklama ishonchli, vijdonli bo''lishi va iste''molchilarni chalg''itmasligi kerak.',
 ARRAY['реклама','достоверность','добросовестность','заблуждение']),
((SELECT id FROM laws WHERE code='UZB-002'), 'Ст. 7',
 'Недобросовестная реклама, содержащая ложные сведения о товарах, услугах или конкурентах, запрещена.',
 'Tovarlar, xizmatlar yoki raqobatchilar haqida yolg''on ma''lumot o''z ichiga olgan vijdonsiz reklama taqiqlanadi.',
 ARRAY['недобросовестная реклама','ложные сведения','конкуренты']),
((SELECT id FROM laws WHERE code='UZB-002'), 'Ст. 12',
 'Реклама алкогольных напитков, табачных изделий запрещена на телевидении, радио и в изданиях для детей.',
 'Alkogol ichimliklar va tamaki mahsulotlari reklamasi televizor, radio va bolalar nashrlarida taqiqlanadi.',
 ARRAY['алкоголь','табак','дети','СМИ','запрет']),
((SELECT id FROM laws WHERE code='UZB-002'), 'Ст. 15',
 'Скрытая реклама, то есть реклама, не обозначенная как таковая и оказывающая неосознанное влияние на потребителей, запрещена.',
 'Yashirin reklama, ya''ni reklama sifatida belgilanmagan va iste''molchilarga ongsiz ta''sir ko''rsatadigan reklama taqiqlanadi.',
 ARRAY['скрытая реклама','маркировка','влияние','потребители']);

-- Articles for UZB-003 (Civil Code)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-003'), 'Ст. 354',
 'Договор считается заключённым, если между сторонами в требуемой форме достигнуто соглашение по всем существенным условиям договора.',
 'Shartnoma tomonlar o''rtasida barcha muhim shartlar bo''yicha kelishuv yuz berganda tuzilgan hisoblanadi.',
 ARRAY['договор','существенные условия','соглашение','заключение']),
((SELECT id FROM laws WHERE code='UZB-003'), 'Ст. 386',
 'Сторона, нарушившая договор, обязана возместить другой стороне причинённые убытки, включая упущенную выгоду.',
 'Shartnomani buzgan tomon boshqa tomonga etkazilgan zararni, shu jumladan boy berilgan foydani qoplashga majbur.',
 ARRAY['нарушение','убытки','возмещение','упущенная выгода']),
((SELECT id FROM laws WHERE code='UZB-003'), 'Ст. 409',
 'Граждане и юридические лица свободны в заключении договора. Понуждение к заключению договора не допускается.',
 'Fuqarolar va yuridik shaxslar shartnoma tuzishda ozod. Shartnoma tuzishga majburlash ruxsat etilmaydi.',
 ARRAY['свобода договора','понуждение','граждане','юридические лица']),
((SELECT id FROM laws WHERE code='UZB-003'), 'Ст. 183',
 'Собственник вправе по своему усмотрению совершать в отношении принадлежащего ему имущества любые действия, не противоречащие закону.',
 'Mulkdor o''z mulkiga nisbatan qonunga zid bo''lmagan har qanday harakatlarni amalga oshirish huquqiga ega.',
 ARRAY['собственник','имущество','право собственности','распоряжение']);

-- Articles for UZB-004 (Tax Code)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-004'), 'Ст. 24',
 'Все налогоплательщики обязаны своевременно и в полном объёме уплачивать установленные налоги и сборы.',
 'Barcha soliq to''lovchilar belgilangan soliq va yig''imlarni o''z vaqtida va to''liq to''lashga majbur.',
 ARRAY['налогоплательщик','уплата','налоги','сборы','обязанность']),
((SELECT id FROM laws WHERE code='UZB-004'), 'Ст. 46',
 'Налоговые льготы предоставляются в соответствии с настоящим кодексом и иными законами. Индивидуальные налоговые льготы не допускаются.',
 'Soliq imtiyozlari ushbu kodeks va boshqa qonunlarga muvofiq beriladi. Individual soliq imtiyozlari ruxsat etilmaydi.',
 ARRAY['налоговые льготы','индивидуальные','освобождение','кодекс']),
((SELECT id FROM laws WHERE code='UZB-004'), 'Ст. 130',
 'Налогом на добавленную стоимость (НДС) облагаются все виды предпринимательской и коммерческой деятельности на территории Республики Узбекистан.',
 'QQS bilan O''zbekiston Respublikasi hududida amalga oshiriladigan barcha tadbirkorlik va tijorat faoliyati soliqqa tortiladi.',
 ARRAY['НДС','добавленная стоимость','предпринимательская деятельность','налогообложение']),
((SELECT id FROM laws WHERE code='UZB-004'), 'Ст. 208',
 'Доходы от деятельности в сфере цифровой экономики и информационных технологий могут облагаться по пониженным ставкам, установленным Кабинетом Министров.',
 'Raqamli iqtisodiyot va axborot texnologiyalari sohasidagi faoliyatdan olingan daromadlar pastroq stavkalar bo''yicha soliqqa tortilishi mumkin.',
 ARRAY['цифровая экономика','IT','пониженные ставки','информационные технологии']);

-- Articles for UZB-005 (Competition)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-005'), 'Ст. 11',
 'Запрещаются соглашения между хозяйствующими субъектами, которые приводят или могут привести к ограничению конкуренции.',
 'Raqobatni cheklashga olib keladigan yoki olib kelishi mumkin bo''lgan xo''jalik yurituvchi sub''ektlar o''rtasidagi kelishuvlar taqiqlanadi.',
 ARRAY['соглашения','ограничение конкуренции','хозяйствующие субъекты','запрет']),
((SELECT id FROM laws WHERE code='UZB-005'), 'Ст. 15',
 'Злоупотребление хозяйствующим субъектом доминирующим положением на рынке запрещено, в том числе установление монопольно высоких цен.',
 'Xo''jalik yurituvchi sub''ektning bozordagi hukmron mavqeidan suiiste''mol qilish, shu jumladan monopol yuqori narxlar belgilash taqiqlanadi.',
 ARRAY['доминирующее положение','монополия','злоупотребление','цены']),
((SELECT id FROM laws WHERE code='UZB-005'), 'Ст. 19',
 'Государство обеспечивает равные условия конкуренции для всех участников рынка независимо от их организационно-правовой формы и формы собственности.',
 'Davlat barcha bozor ishtirokchilari uchun tashkiliy-huquqiy shaklidan qat''i nazar teng raqobat sharoitlarini ta''minlaydi.',
 ARRAY['равные условия','государство','участники рынка','конкуренция']);

-- Articles for UZB-006 (Labour Code)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-006'), 'Ст. 80',
 'Нормальная продолжительность рабочего времени не может превышать 40 часов в неделю. Для отдельных категорий работников устанавливается сокращённая рабочая неделя.',
 'Normal ish vaqtining davomiyligi haftasiga 40 soatdan oshmasligi kerak.',
 ARRAY['рабочее время','40 часов','неделя','продолжительность']),
((SELECT id FROM laws WHERE code='UZB-006'), 'Ст. 153',
 'Размер заработной платы работника не может быть ниже установленного законодательством минимального размера оплаты труда.',
 'Xodim ish haqining miqdori qonun hujjatlarida belgilangan eng kam ish haqidan past bo''lishi mumkin emas.',
 ARRAY['минимальная заработная плата','МРОТ','оплата труда','работник']),
((SELECT id FROM laws WHERE code='UZB-006'), 'Ст. 97',
 'Работники имеют право на ежегодный оплачиваемый основной отпуск продолжительностью не менее 15 рабочих дней.',
 'Xodimlar kamida 15 ish kuni davomida yillik haqli asosiy ta''tilga haq ega.',
 ARRAY['ежегодный отпуск','оплачиваемый','15 дней','право']),
((SELECT id FROM laws WHERE code='UZB-006'), 'Ст. 105',
 'Запрещается принудительный труд, дискриминация в сфере труда и занятости по любым основаниям, не связанным с деловыми качествами работника.',
 'Majburiy mehnat, mehnat va bandlik sohasida xodimning ish fazilatlari bilan bog''liq bo''lmagan har qanday asoslarda kamsitish taqiqlanadi.',
 ARRAY['принудительный труд','дискриминация','запрет','равенство']);

-- Articles for UZB-007 (E-Commerce)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-007'), 'Ст. 8',
 'Электронный договор, заключённый с использованием электронной цифровой подписи, имеет юридическую силу, равную договору в письменной форме.',
 'Elektron raqamli imzo yordamida tuzilgan elektron shartnoma yozma shakldagi shartnoma bilan teng yuridik kuchga ega.',
 ARRAY['электронный договор','ЭЦП','юридическая сила','письменная форма']),
((SELECT id FROM laws WHERE code='UZB-007'), 'Ст. 12',
 'Продавец обязан предоставить покупателю полную информацию о товаре, включая цену, условия доставки и возврата, до заключения электронной сделки.',
 'Sotuvchi elektron bitim tuzilgunga qadar xaridorga tovar, narx, yetkazib berish va qaytarish shartlari haqida to''liq ma''lumot berishga majbur.',
 ARRAY['информация о товаре','цена','доставка','возврат','электронная торговля']),
((SELECT id FROM laws WHERE code='UZB-007'), 'Ст. 17',
 'Оператор электронной торговой площадки обязан обеспечить защиту персональных данных покупателей и конфиденциальность их финансовой информации.',
 'Elektron savdo maydonchasi operatori xaridorlarning shaxsiy ma''lumotlarini va moliyaviy ma''lumotlarining maxfiyligini ta''minlashga majbur.',
 ARRAY['персональные данные','конфиденциальность','финансовая информация','оператор']);

-- Articles for UZB-008 (Personal Data)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-008'), 'Ст. 6',
 'Обработка персональных данных допускается только с письменного согласия субъекта персональных данных, за исключением случаев, прямо предусмотренных законом.',
 'Shaxsiy ma''lumotlarni qayta ishlash faqat shaxsiy ma''lumotlar sub''ektining yozma roziligiga asosan amalga oshirilishi mumkin.',
 ARRAY['согласие','обработка','персональные данные','письменное согласие']),
((SELECT id FROM laws WHERE code='UZB-008'), 'Ст. 14',
 'Субъект персональных данных вправе требовать от оператора исправления недостоверных данных, удаления данных либо прекращения их обработки.',
 'Shaxsiy ma''lumotlar sub''ekti operatordan noto''g''ri ma''lumotlarni to''g''rilash, o''chirish yoki qayta ishlanishini to''xtatishni talab qilish huquqiga ega.',
 ARRAY['право','исправление','удаление','прекращение обработки']),
((SELECT id FROM laws WHERE code='UZB-008'), 'Ст. 20',
 'Оператор обязан принять организационные и технические меры для защиты персональных данных от несанкционированного доступа, утечки и уничтожения.',
 'Operator shaxsiy ma''lumotlarni ruxsatsiz kirish, sizib chiqish va yo''q qilishdan himoya qilish uchun tashkiliy va texnik choralar ko''rishga majbur.',
 ARRAY['защита','несанкционированный доступ','утечка','технические меры']);

-- Articles for UZB-009 (Education)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-009'), 'Ст. 4',
 'Государственные общеобразовательные учреждения обеспечивают бесплатное обязательное образование. Частные учреждения могут взимать плату за обучение.',
 'Davlat umumta''lim muassasalari bepul majburiy ta''limni ta''minlaydi. Xususiy muassasalar o''qish uchun to''lov olishi mumkin.',
 ARRAY['бесплатное образование','государственные','обязательное','частные']),
((SELECT id FROM laws WHERE code='UZB-009'), 'Ст. 11',
 'Частные образовательные учреждения осуществляют деятельность на основании лицензии и обязаны соответствовать государственным образовательным стандартам.',
 'Xususiy ta''lim muassasalari litsenziya asosida faoliyat yuritadi va davlat ta''lim standartlariga javob berishi shart.',
 ARRAY['лицензия','частные','образовательные стандарты','государственные']),
((SELECT id FROM laws WHERE code='UZB-009'), 'Ст. 28',
 'Запрещается любая форма дискриминации в сфере образования по национальному, расовому, религиозному или иному признаку.',
 'Ta''lim sohasida milliy, irqiy, diniy yoki boshqa belgilarga ko''ra har qanday shaklda kamsitish taqiqlanadi.',
 ARRAY['дискриминация','образование','запрет','равные права']);

-- Articles for UZB-010 (Environment)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-010'), 'Ст. 16',
 'Предприятия и организации при осуществлении хозяйственной деятельности обязаны соблюдать экологические нормативы и не допускать загрязнения окружающей среды.',
 'Korxonalar va tashkilotlar xo''jalik faoliyatini amalga oshirishda ekologik me''yorlarga rioya qilishi va atrof-muhitni ifloslantirmaslik shart.',
 ARRAY['экологические нормативы','загрязнение','предприятия','хозяйственная деятельность']),
((SELECT id FROM laws WHERE code='UZB-010'), 'Ст. 23',
 'Государственная экологическая экспертиза является обязательной для всех проектов хозяйственной деятельности, способных оказать воздействие на окружающую среду.',
 'Davlat ekologik ekspertizasi atrof-muhitga ta''sir ko''rsatishi mumkin bo''lgan barcha xo''jalik faoliyati loyihalari uchun majburiydir.',
 ARRAY['экологическая экспертиза','обязательная','проекты','воздействие']),
((SELECT id FROM laws WHERE code='UZB-010'), 'Ст. 31',
 'Граждане имеют право на благоприятную окружающую среду, достоверную информацию о её состоянии и на возмещение ущерба, причинённого экологическими правонарушениями.',
 'Fuqarolar qulay atrof-muhitga, uning holati haqida ishonchli ma''lumotga va ekologik huquqbuzarliklar natijasida etkazilgan zararni qoplashga haqli.',
 ARRAY['право граждан','благоприятная среда','информация','возмещение ущерба']);

-- Articles for UZB-011 (Banking)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-011'), 'Ст. 12',
 'Банки осуществляют деятельность на основании лицензии Центрального банка Республики Узбекистан. Осуществление банковских операций без лицензии запрещено.',
 'Banklar O''zbekiston Respublikasi Markaziy bankining litsenziyasi asosida faoliyat yuritadi.',
 ARRAY['банк','лицензия','Центральный банк','банковские операции']),
((SELECT id FROM laws WHERE code='UZB-011'), 'Ст. 28',
 'Банки обязаны соблюдать нормативы достаточности капитала, ликвидности и иные пруденциальные нормативы, установленные Центральным банком.',
 'Banklar Markaziy bank tomonidan belgilangan kapital yetarliligi va likvidlik normativlariga rioya qilishga majbur.',
 ARRAY['капитал','ликвидность','пруденциальные нормативы','Центральный банк']),
((SELECT id FROM laws WHERE code='UZB-011'), 'Ст. 45',
 'Криптовалюты и иные цифровые финансовые активы не являются законным платёжным средством на территории Республики Узбекистан, если иное не установлено законом.',
 'Kriptovalyutalar va boshqa raqamli moliyaviy aktivlar qonun boshqacha belgilamasa, O''zbekiston Respublikasi hududida qonuniy to''lov vositasi hisoblanmaydi.',
 ARRAY['криптовалюта','цифровые активы','платёжное средство','запрет']);

-- Articles for UZB-012 (Business)
INSERT INTO law_articles (law_id, article_num, content_ru, content_uz, keywords) VALUES
((SELECT id FROM laws WHERE code='UZB-012'), 'Ст. 6',
 'Субъекты предпринимательства подлежат государственной регистрации в порядке, установленном законодательством. Деятельность без регистрации запрещена.',
 'Tadbirkorlik sub''ektlari qonun hujjatlarida belgilangan tartibda davlat ro''yxatidan o''tkazilishi kerak.',
 ARRAY['государственная регистрация','предпринимательство','обязательная','деятельность']),
((SELECT id FROM laws WHERE code='UZB-012'), 'Ст. 14',
 'Государство гарантирует защиту прав и законных интересов предпринимателей, недопустимость незаконного вмешательства государственных органов в их деятельность.',
 'Davlat tadbirkorlarning huquqlari va qonuniy manfaatlarini himoya qilishni, davlat organlarining ularning faoliyatiga noqonuniy aralashuvining yo''ql ligini kafolatlaydi.',
 ARRAY['защита прав','предприниматели','государственные органы','вмешательство']),
((SELECT id FROM laws WHERE code='UZB-012'), 'Ст. 22',
 'Предпринимательская деятельность в отдельных сферах требует получения специального разрешения (лицензии) в соответствии с перечнем, утверждённым Кабинетом Министров.',
 'Ayrim sohalardagi tadbirkorlik faoliyati Vazirlar Mahkamasi tomonidan tasdiqlangan ro''yxatga muvofiq maxsus ruxsatnoma (litsenziya) olishni talab qiladi.',
 ARRAY['лицензия','специальное разрешение','отдельные сферы','Кабинет Министров']);

-- Helper view for full-text search
CREATE OR REPLACE VIEW laws_full_text AS
SELECT
    l.id,
    l.code,
    l.title_ru,
    l.title_uz,
    l.category,
    l.year,
    l.summary_ru,
    l.summary_uz,
    string_agg(a.content_ru, ' ') AS all_articles_ru,
    string_agg(a.article_num || ': ' || a.content_ru, ' | ') AS articles_with_nums,
    to_tsvector('russian', coalesce(l.title_ru,'') || ' ' || coalesce(l.summary_ru,'') || ' ' || coalesce(string_agg(a.content_ru, ' '),'')) ||
    to_tsvector('simple',  coalesce(l.title_uz,'') || ' ' || coalesce(l.summary_uz,'') || ' ' || coalesce(string_agg(a.content_uz, ' '),''))
    AS search_vector
FROM laws l
LEFT JOIN law_articles a ON a.law_id = l.id
WHERE l.is_active = TRUE
GROUP BY l.id, l.code, l.title_ru, l.title_uz, l.category, l.year, l.summary_ru, l.summary_uz;
