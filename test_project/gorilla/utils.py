from __future__ import annotations

import math


def calculate_fighter_rank(
    rank_points: float,
    age: int,
    weight: float,
    height: float,
) -> dict[str, str | int | float]:
    score = rank_points + (weight * 5) + (height * 100) - (age * 10)
    rounded_score = round(score, 1)

    if score >= 10000:
        return {
            'rank': 'Legendary Champion',
            'tier': 'S',
            'color': '#FFD700',
            'description': 'A once-in-a-generation fighter who dominates every arena.',
            'score': rounded_score,
        }
    elif score >= 7000:
        return {
            'rank': 'Grandmaster',
            'tier': 'A',
            'color': '#C0C0C0',
            'description': 'An elite warrior feared across all fighting circuits.',
            'score': rounded_score,
        }
    elif score >= 4000:
        return {
            'rank': 'Champion',
            'tier': 'B',
            'color': '#CD7F32',
            'description': 'A proven champion ready for the biggest stages.',
            'score': rounded_score,
        }
    elif score >= 2000:
        return {
            'rank': 'Contender',
            'tier': 'C',
            'color': '#4682B4',
            'description': 'A rising contender with serious potential.',
            'score': rounded_score,
        }
    elif score >= 1000:
        return {
            'rank': 'Fighter',
            'tier': 'D',
            'color': '#708090',
            'description': 'A solid fighter still climbing the ranks.',
            'score': rounded_score,
        }
    else:
        return {
            'rank': 'Rookie',
            'tier': 'E',
            'color': '#A0522D',
            'description': 'A fresh recruit with the heart of a warrior.',
            'score': rounded_score,
        }


def generate_introduction(
    name: str,
    fight_style: str,
) -> dict[str, str]:
    intros = {
        'box': f"Ladies and gentlemen, in this corner weighing in with precision and power — {name}, the master of boxing!",
        'mua': f"From the temples of Thailand, a warrior of the eight limbs — {name}, the Muay Thai legend!",
        'bjj': f"With the patience of a coiled serpent and the grip of iron — {name}, Brazilian Jiu-Jitsu specialist!",
        'wre': f"Unstoppable force meets immovable object — {name}, the wrestling powerhouse!",
        'kar': f"Discipline. Precision. Devastation. Introducing {name}, the Karate master!",
        'tae': f"With lightning kicks that shatter the air — {name}, the Taekwondo warrior!",
        'jud': f"The art of flexibility and leverage — {name}, the Judo champion!",
        'kic': f"Where boxing meets destruction — {name}, the kickboxing fury!",
        'mix': f"Master of every style, feared in every ring — {name}, the mixed martial arts beast!",
        'bra': f"No rules. No mercy. Pure instinct — {name}, the undisputed brawler!",
    }

    return {
        'introduction': intros.get(
            fight_style,
            f"Step into the arena — {name}, the fearless warrior!",
        ),
        'style': fight_style,
    }


def predict_fight_outcome(
    red_power: float,
    blue_power: float,
) -> dict[str, str | int]:
    red_power = float(red_power)
    blue_power = float(blue_power)

    total = red_power + blue_power
    if total <= 0:
        return {
            'winner': 'Draw',
            'confidence': 50,
            'prediction': 'Two evenly matched rookies — this could go either way!',
            'margin': 0,
        }

    red_pct = (red_power / total) * 100
    blue_pct = (blue_power / total) * 100
    margin = abs(red_pct - blue_pct)

    if margin < 5:
        winner = 'Draw (Too Close to Call)'
        confidence = 30
        prediction = 'These fighters are neck and neck — the crowd will be on their feet!'
    elif red_pct > blue_pct:
        winner = 'Red Corner'
        confidence = min(math.ceil(margin * 1.5), 95)
        prediction = f'Red Corner has the edge with {red_pct:.1f}% power advantage!'
    else:
        winner = 'Blue Corner'
        confidence = min(math.ceil(margin * 1.5), 95)
        prediction = f'Blue Corner has the edge with {blue_pct:.1f}% power advantage!'

    return {
        'winner': winner,
        'confidence': confidence,
        'prediction': prediction,
        'margin': round(margin, 1),
    }
