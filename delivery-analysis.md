# Analysing Delivery Data
Delivery volume indicates the total number of shares carried forward to the next day.

A trader taking delivery of a stock expects the price to move up in the next few days.

An unusually high delivery volume indicates a bullish sentiment toward the stock.

## Delivery percentage can be misleading.
Most websites tend to compare delivery % to its 15 or 30-day average.
> Delivery % = Delivery volume / Total volume * 100

**Let's take an example to illustrate the problem**
Day 1, a stock has 50K delivery and 100K total volume,
a 50% delivery (50K / 100K * 100).

Day 2, the same stock has a 100K delivery against a 200K total volume. Again 50% delivery!

A significant spike in delivery volume on day 2, yet the delivery % fails to show this.

Comparing the Delivery % to the previous day's average is problematic. The article below explains-
[Why you should be careful when averaging percentages](https://www.robertoreif.com/blog/2018/1/7/why-you-should-be-careful-when-averaging-percentages)

## How do we calculate delivery data?
On 24th August 2022, HDFCBANK had a delivery Qty of 46,89,197.

The average delivery Qty of the last 60 days is 39,14,991. We notice the delivery Qty is above average.

To make it easier to analyze, we divide the delivery Qty and Average delivery Qty
> 46,89,197 / 39,14,991 = ~1.2
Value > 1: Above average
Value < 1: Below average
