# Theme Park Speedruninator
## IA626 Final Project

The Theme Park Speedruninator is a tool which uses historical data to determine the optimal route through a theme park, experiencing every attraction in a minimum amount of time. The user provides a desired park, how much historical data should be considered (past week, month, quarter, year, weekends vs. weekdays), potential weather conditions (optional), alternate queue lines (such as single rider), and desired walking speed. The Speedruninator will determine a route which starts and ends at the main entrance to the theme park, visits each attraction exactly once, and factors in the time taken to walk between attractions, wait in line for each attraction, and ride the attraction. If weather information is provided, only data from dates with similar weather conditions will be considered (temperature, sunny, cloudy, rainy) to provide an accurate estimation.

The primary data source for this project will be the [ThemeParks.wiki API](https://themeparks.wiki/), which provides current wait times for rides at many large theme parks around the world. For this project, I will be focusing on the following parks:

- Walt Disney World
    - Magic Kingdom Park
    - EPCOT
    - Disney's Animal Kingdom
    - Disney's Hollywood Studios
    - Disney's Typhoon Lagoon Water Park
    - Disney's Blizzard Beach Water Park
- Disneyland Resort
    - Disneyland Park
    - Disney California Adventure Park
- Tokyo Disney Resort
    - Tokyo DisneySea
    - Tokyo Disneyland
- Disneyland Paris
    - Disneyland Park
    - Walt Disney Studios Park
- Hong Kong Disneyland Park
- Shanghai Disneyland

Between these parks, there are 299 total attractions which I have been caching the wait times from this API for over a month, recording over 100,000 queue durations in that period.
