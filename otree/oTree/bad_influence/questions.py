colors = {
    "red": "/static/main_platform/otree/media/peeps/red_peep.png",
    "blue": "/static/main_platform/otree/media/peeps/blue_peep.png",
    "pink": "/static/main_platform/otree/media/peeps/pink_peep.png",
    "yellow": "/static/main_platform/otree/media/peeps/yellow_peep.png",
    "grey": "/static/main_platform/otree/media/peeps/grey_peep.png",
    "green": "/static/main_platform/otree/media/peeps/green_peep.png",
}

color_pairs = [('red','blue'), ('blue','yellow'), ('yellow','red'), ('green','blue'),
               ('blue','red'), ('yellow','blue'), ('red','yellow'), ('blue','green'),
               ('red','blue'), ('blue','yellow'), ('yellow','red'), ('green','blue'),
               ('blue','red'), ('yellow','blue'), ('red','yellow'), ('blue','green')
               ]

def kontrol(hub, gender, number_of_friends):
    minority_choice = "rød"
    majority_choice = "blå"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Farver',
        'text': "Du kan vælge mellem farverne rød og blå.",
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text_1': "De blå ansigter repræsenterer dem som ikke tror klimaforandringerne er menneskeskabte",
        'result_page_text_2': "De røde ansigter repræsenterer dem som tror klimaforandringerne er menneskeskabte",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'majority_choice': majority_choice,
        'minority_choice': minority_choice,
        'minority_color_img': colors[color_pairs[0][0]],
        'majority_color_img': colors[color_pairs[0][1]]
    }


def studietur(hub, gender, number_of_friends):
    minority_choice = "er at tage til Rom"
    majority_choice = "er at tage til Paris"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Studietur',
        'text': "I skal på studietur, og I kan vælge mellem Rom og Paris.",
        'preference':
            ("Din præference {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text_1': "De blå ansigter repræsenterer dem som vil på studietur til Rom.",
        'result_page_text_2': "De gule ansigter repræsenterer dem som vil på studietur til Paris.",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'minority_choice': "Rom",
        'majority_choice': "Paris",
        'minority_color_img': colors[color_pairs[1][0]],
        'majority_color_img': colors[color_pairs[1][1]]
    }


def matematik(hub, gender, number_of_friends):
    minority_choice = "mobbe ham"
    majority_choice = "ikke mobbe ham"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Matematiklæreren',
        'text':
            ("I har fået en ny matematiklærer, og han er lidt speciel. " +
             "I kan vælge at mobbe ham kollektivt eller ikke at mobbe ham."),
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text_1': "De røde ansigter repræsenterer dem som har valgt ikke at mobbe den nye matematiklærer.",
        'result_page_text_2': "De gule ansigter repræsenterer dem som har valgt at mobbe den nye matematiklærer.",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'minority_choice': "Rom",
        'minority_choice': "mobbe",
        'majority_choice': "ikke mobbe",
        'minority_color_img': colors[color_pairs[2][0]],
        'majority_color_img': colors[color_pairs[2][1]]
    }


def hpv(hub, gender, number_of_friends):
    minority_choice = "du vil ikke vaccineres"
    majority_choice = "du vil gerne vaccineres"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'HPV',
        'text':
            ("Du har fået et tilbud på en gratis vaccination mod hpv."),
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
         'result_page_text_1': "De blå ansigter repræsenterer dem som gerne vil vaccineres mod HPV.",
        'result_page_text_2': "De grønne ansigter repræsenterer dem som ikke vil vaccineres mod HPV.",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'minority_choice': "vil ikke",
        'majority_choice': "vil gerne",
        'minority_color_img': colors[color_pairs[3][0]],
        'majority_color_img': colors[color_pairs[3][1]]
    }


def billeddeling(hub, gender, number_of_friends):
    minority_choice = "dele billedet med andre"
    majority_choice = "ikke dele billedet med andre"
    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Nøgenbillede',
        'text':
            ("I har fået fat i et nøgenbillede af en irriterende pige fra parallelklassen. " +
             "I kan vælge at dele det med andre i og uden for skolen eller lade være."),
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
         'result_page_text_1': "De blå ansigter repræsenterer dem som har valgt at dele nøgenbilledet.",
        'result_page_text_2': "De røde ansigter repræsenterer dem som har valgt ikke at dele nøgenbilledet.",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'minority_choice': "dele",
        'majority_choice': "ikke dele",
        'minority_color_img': colors[color_pairs[4][0]],
        'majority_color_img': colors[color_pairs[4][1]]
    }


def stikkeri(hub, gender, number_of_friends, city):
    minority_choice = "sige det"
    majority_choice = "holde mund"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Oscar og William',
        'text':
             ("Jeres længe ventede studietur til {city} er i fare for at blive aflyst, " +
             "fordi nogle af eleverne har røget hash på skolens område. " +
             "Lærerne har bedt alle i klassen om at angive de personer, der gjorde det. " +
             "Lærerne truer med at aflyse studieturen, hvis ingen siger noget. " +
             "I ved godt, at det var Oscar og William der delte en joint sidste fredag i skolegården. " +
             "I kan vælge at udlevere deres navne til lærerne eller at holde mund.").format(city=city),
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text_1': "De blå ansigter repræsenterer dem som har valgt ikke at sladre til lærerne.",
        'result_page_text_2': "De gule ansigter repræsenterer dem som har valgt at sladre til lærerne.",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'minority_choice': "sig det",
        'majority_choice': "hold mund",
        'minority_color_img': colors[color_pairs[5][0]],
        'majority_color_img': colors[color_pairs[5][1]]
    }


def alkohol(hub, gender, number_of_friends):
    minority_choice = "der skal smugles!"
    majority_choice = "ikke smugle."

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Sprut',
        'text':
             ("I skal holde fest på skolen på fredag, " +
             "og I skal aftale om I vil smugle sprut med til festen, " +
             "eller om i vil respektere skolens alkoholpolitik og lade være."),
        'preference':
            ("Din præference: {prefers}")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
                'result_page_text_1': "De røde ansigter repræsenterer dem som har valgt at smugle sprut med til festen. ",
        'result_page_text_2': "De gule ansigter repræsenterer dem som har valgt ikke at smugle sprut med til festen.",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'minority_choice': "smugle",
        'majority_choice': "ikke smugle",
        'minority_color_img': colors[color_pairs[6][0]],
        'majority_color_img': colors[color_pairs[6][1]]
    }


def klima(hub, gender, number_of_friends):
    minority_choice = "du tror ikke på at klimaforandringerne er menneskeskabte"
    majority_choice = "du tror selvfølgelig på at klimaforandringerne er menneskeskabte"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Klimaforandringer',
        'text':
             ("Der er uenighed om, hvorvidt klimaforandringerne " +
             "er menneskeskabte eller ej."),
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
                        'result_page_text_1': "De blå ansigter repræsenterer dem som ikke tror klimaforandringerne er menneskeskabte",
        'result_page_text_2': "De grønne ansigter repræsenterer dem som tror klimaforandringerne er menneskeskabte",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'majority_choice': "menneskeskabte",
        'minority_choice': "naturlige",
        'minority_color_img': colors[color_pairs[7][0]],
        'majority_color_img': colors[color_pairs[7][1]]
    }


def sexchikane(hub, gender, number_of_friends):
    minority_choice = "at ignorere det"
    majority_choice = "at sige det"
    male = "drengene"
    female = "pigerne"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)
    koen = male if gender else female

    return {
        'title': 'Sexchikane',
        'text':
             ("Den søde vikar, som altid giver jer lov til at se film i tysktimerne, har lagt an på nogle af {koen} i klassen. " +
             "I kan vælge at sige det til rektor, men da risikerer I, at vikaren bliver fyret. " +
             "Eller I kan lade som ingenting med risiko for at vikaren bare forsætter.")
                .format(koen=koen),
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
                             'result_page_text_1': "De blå ansigter repræsenterer dem som har valgt at sige det til rektoren. ",
        'result_page_text_2': "De røde ansigter repræsenterer dem som har valgt ikke at sige det til rektoren. ",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'minority_choice': "ignorér",
        'majority_choice': "sig det",
        'minority_color_img': colors[color_pairs[8][0]],
        'majority_color_img': colors[color_pairs[8][1]]
    }


def moon(hub, gender, number_of_friends):
    minority_choice = "du tror ikke på at amerikanerne landede på månen"
    majority_choice = "du tror selvfølgelig på at amerikanerne landede på månen"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Månelanding',
        'text':
             ("Der er uenighed om, hvorvidt amerikanerne " +
             "faktisk landede på månen eller ej."),
        'preference':
            ("Din præference: {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text_1': "De blå ansigter repræsenterer dem som ikke tror på månelandingen. ",
        'result_page_text_2': "De gule ansigter repræsenterer dem som tror på månelandingen.",
        'graph_explanation': "Hvis den blå linje overstiger 50%, har det oprindelige mindretal formået at snyde det oprindelig flertal til at hoppe på en konspirationsteori.",
        'face_explanation': "Klik på ansigterne for at se de individuelle venne-netværk. Klik igen for at se hele netværket. ",
        'stubbornness': "Stædighed (i sekunder) angiver hvor længe en spiller har bibeholdt sin præference når spilleren var i mindretal i venne-netværket. Det giver et praj om, hvor stædig spilleren forsøgte at få de andre til at skifte mening. Stædigheden antages at korrelere med de opnåede antal point. ",
        'majority_choice': "tror på det",
        'minority_choice': "tror det ikke",
        'minority_color_img': colors[color_pairs[9][0]],
        'majority_color_img': colors[color_pairs[9][1]]
    }


questions = {
    'kontrol': kontrol,
    'studietur': studietur,
    'matematik': matematik,
    'hpv': hpv,
    'billeddeling': billeddeling,
    'stikkeri': stikkeri,
    'alkohol': alkohol,
    'klima': klima,
    'sexchikane': sexchikane,
    'moon': moon,
}

question_order = {
    1: 'kontrol',
    2: 'studietur',
    3: 'matematik',
    4: 'hpv',
    5: 'billeddeling',
    6: 'stikkeri',
    7: 'alkohol',
    8: 'klima',
    9: 'sexchikane',
    10: 'moon',
}


def make_question(group, is_hub, gender, number_of_friends):
    if group.question == 'stikkeri':
        return stikkeri(is_hub, gender, number_of_friends, "Rom" if group.in_round(2).choice else "Paris")
    return questions[group.question](is_hub, gender, number_of_friends)
