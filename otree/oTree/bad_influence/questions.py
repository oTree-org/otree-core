colors = {
    "red": "/static/media/red_peep.png",
    "blue": "/static/media/blue_peep.png",
    "pink": "/static/media/pink_peep.png",
    "yellow": "/static/media/yellow_peep.png",
    "grey": "/static/media/grey_peep.png",
    "green": "/static/media/green_peep.png",
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
        'result_page_text': "(Du kan vælge mellem rød og blå.)",
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
        'result_page_text': "(I skal på studietur, og I kan vælge mellem Rom og Paris.)",
        'minority_choice': "Rom",
        'majority_choice': "Paris",
        'minority_color_img': colors[color_pairs[1][0]],
        'majority_color_img': colors[color_pairs[1][1]]
    }


def matematik(hub, gender, number_of_friends):
    minority_choice = "er at mobbe ham"
    majority_choice = "er ikke at mobbe ham"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Matematiklæreren',
        'text':
            ("I har fået en ny matematiklærer, og han er lidt speciel. " +
             "I kan vælge at mobbe ham kollektivt eller ikke at mobbe ham."),
        'preference':
            ("Din præference {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text':
             "(I har fået en ny matematiklærer, og han er lidt speciel. " +
             "I kan vælge at mobbe ham kollektivt eller ikke at mobbe ham.)",
        'minority_choice': "mobbe",
        'majority_choice': "ikke mobbe",
        'minority_color_img': colors[color_pairs[2][0]],
        'majority_color_img': colors[color_pairs[2][1]]
    }


def hpv(hub, gender, number_of_friends):
    minority_choice = "ikke vaccineres"
    majority_choice = "gerne vaccineres"

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'HPV',
        'text':
            ("Du har fået et tilbud på en gratis vaccination mod hpv."),
        'preference':
            ("Du vil {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text':
             "(Du har fået et tilbud på en gratis vaccination mod hpv.)",
        'minority_choice': "vil ikke",
        'majority_choice': "vil gerne",
        'minority_color_img': colors[color_pairs[3][0]],
        'majority_color_img': colors[color_pairs[3][1]]
    }


def billeddeling(hub, gender, number_of_friends):
    minority_choice = "er at dele billedet"
    majority_choice = "er ikke at dele billedet"
    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Nøgenbillede',
        'text':
            ("I har fået tilsendt et nøgenbillede af en irriterende pige fra parallelklassen. " +
             "I kan vælge at dele det med andre i og uden for skolen eller lade være."),
        'preference':
            ("Din præference {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text':
             "(I har fået tilsendt et nøgenbillede af en irriterende pige fra parallelklassen. " +
             "I kan vælge at dele det med andre i og uden for skolen eller lade være.)",
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
            ("Din præference er at {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text':
             "(Jeres længe ventede studietur til {city} er i fare for at blive aflyst, " +
             "fordi nogle af eleverne har røget hash på skolens område. " +
             "Lærerne har bedt alle i klassen om at angive de personer, der gjorde det. " +
             "Lærerne truer med at aflyse studieturen, hvis ingen siger noget. " +
             "Alle jer i klassen ved godt, at det var Oscar og William der delte en joint sidste fredag i skolegården. " +
             "I kan vælge at udlevere deres navne til lærerne eller at holde mund.)".format(city=city),
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
        'result_page_text':
             "(I skal holde fest på skolen på fredag, " +
             "og I skal aftale om I vil smugle sprut med til festen, " +
             "eller om i vil respektere skolens alkoholpolitik og lade være.)",
        'minority_choice': "smugle",
        'majority_choice': "ikke smugle",
        'minority_color_img': colors[color_pairs[6][0]],
        'majority_color_img': colors[color_pairs[6][1]]
    }


def klima(hub, gender, number_of_friends):
    minority_choice = "ikke"
    majority_choice = ""

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Klimaforandringer',
        'text': "",
        'preference':
            ("Du tror faktisk {prefers} på at klimaforandringerne er menneskeskabte.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text':
             "(Du tror {ikke | } på at klimaforandringerne er menneskeskabte.)",
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
            ("Din præference er {prefers}.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text':
             "(Den søde vikar, som altid giver jer lov til at se film i tysktimerne, har lagt an på nogle af {drengene | pigerne} i klassen. " +
             "I kan vælge at fortælle det til rektor, men da risikerer I, at vikaren bliver fyret. " +
             "Eller I kan lade som ingenting med risiko for at vikaren forsætter sin adfærd.)",
        'minority_choice': "ignorér",
        'majority_choice': "sig det",
        'minority_color_img': colors[color_pairs[8][0]],
        'majority_color_img': colors[color_pairs[8][1]]
    }


def moon(hub, gender, number_of_friends):
    minority_choice = "ikke"
    majority_choice = ""

    prefers, other = (minority_choice, majority_choice) if hub else (majority_choice, minority_choice)

    return {
        'title': 'Månelanding',
        'text': "",
        'preference':
            ("Du tror selvfølgelig {prefers} på at amerikanerne landede på månen.")
                .format(prefers=prefers, other=other),
        'challenge':
            ("Du får 3 point hvis det du vælger får flertal i klassen. " +
             "Du får {num} point ekstra hvis dit valg svarer til din præference.")
                .format(num=number_of_friends),
        'result_page_text':
             "(Du tror selvfølgelig {ikke | } på at amerikanerne landede på månen.)",
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
