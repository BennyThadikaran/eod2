# Analysing Delivery Data
Delivery volume indicates the total number of shares carried forward to the next day.

An unusually high delivery volume indicates a bullish sentiment toward the stock.

Most websites tend to compare delivery % to its 15 or 30-day average.
> Delivery % = Delivery volume / Total volume * 100

## Delivery percentage can be misleading.
Let's take an example to illustrate the problem

|   |Delivery Volume|Total Volume|Delivery %|
| ------------ | ------------ | ------------ | ------------ |
|Day 1|50,000|100,000|50 %|
|Day 2|100,000|200,000|50 %|

A significant spike in delivery volume on day 2, yet the delivery % fails to show this.

Averaging percentages can be problematic as is explained in this article [Why you should be careful when averaging percentages](https://www.robertoreif.com/blog/2018/1/7/why-you-should-be-careful-when-averaging-percentages)

## How do we calculate delivery data?

We take a ratio of the delivery quantity to its historical average over the last 30 or 60 or 90 days.

> Today's Delivery Qty / Average Delivery Qty

**A ratio above 1 indicates above average delivery and vice versa.**

## Calculation of Qty per trade

NSE provided a 'Total traded quantity' in their daily bhavcopy. This is different from 'Total volume'

> Qty per trade = total volume / total traded quantity

We again take a ratio of Qty per trade with its historical average.

**An above average delivery and qty per trade could indicate an important price zone in the market.**

![screenshot](/images/dget.png)

In the screenshot above, you can see Godrej Industries, Marksans Pharma and Tatapower have higher than average qty per trade and delivery.
