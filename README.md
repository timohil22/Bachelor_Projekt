# Bargaining Experiment – Incomplete Information about Discount Rates

This repository contains the source code for a web-based bargaining experiment developed to study negotiation behavior under asymmetric time preferences and incomplete information about discount rates.

The experiment implements a bilateral bargaining game based on the theoretical bargaining framework introduced by **Rubinstein (1982)** and its continuous-time modification by **Perry and Reny (1993)**.


## Theoretical Background

The bargaining environment implemented in this experiment is derived from the **alternating-offers bargaining model** of Rubinstein (1982). In this model, two players bargain over the division of a surplus while both players discount future payoffs.

A central implication of the Rubinstein model is that **relative patience determines bargaining power**: the player with the lower discount rate (i.e., the more patient player) obtains a larger share of the surplus in equilibrium.

To better capture real negotiation environments where offers can occur at arbitrary points in time, the experiment adopts the **continuous-time extension of the Rubinstein model proposed by Perry and Reny (1993)**. In this formulation:

- bargaining takes place in continuous time
- offers can be made at any moment
- payoffs decline over time according to individual discount rates

As a consequence, delays in reaching an agreement generate **time-dependent negotiation costs**, which affect the effective division of the surplus.


## Experimental Design

The experiment investigates how bargaining outcomes change when players have **asymmetric discount rates** and when information about these discount rates is **complete or incomplete**.

Three treatments are implemented:

### Treatment 1 – Baseline

- symmetric discount rates  
- complete information  
- equal bargaining power  

### Treatment 2 – Asymmetric Discount Rates (Complete Information)

- players have different discount rates  
- both players observe the opponent’s discount rate  
- the more patient player has a structural bargaining advantage  

### Treatment 3 – Asymmetric Discount Rates (Incomplete Information)

- discount rates remain asymmetric  
- players only observe their own discount rate  
- the opponent’s time preference is private information  

This design allows the experiment to examine:

- whether players exploit the theoretical bargaining advantage implied by the model
- how incomplete information affects negotiation behavior
- how negotiation duration affects effective payoffs


## Features

The platform implements:

- real-time bilateral negotiations
- time-dependent discounting of payoffs
- automatic matching of participants
- treatment assignment
- logging of negotiation actions
- a post-experiment questionnaire

The system records relevant variables such as:

- opening offers
- accepted prices
- negotiation duration
- player roles
- treatment assignment
- questionnaire responses

These data are used for statistical analysis of bargaining behavior.


## Research Questions

The experiment is designed to investigate:

- whether asymmetric discount rates translate into bargaining power in practice
- how incomplete information about time preferences affects negotiation outcomes
- whether players exploit structural bargaining advantages
- whether outcomes from a preliminary test negotiation act as anchors for opening offers in later negotiations



## References

Rubinstein, A. (1982). *Perfect equilibrium in a bargaining model*. Econometrica, 50(1), 97–109.

Perry, M., & Reny, P. (1993). *A non-cooperative bargaining model with strategically timed offers*. Journal of Economic Theory, 59(1), 50–77.

---

## License

This repository is provided for research and educational purposes.
