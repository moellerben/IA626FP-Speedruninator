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

Between these parks, there are 299 total attractions which I have been caching the wait times from this API for over a month via a PHP cron job, recording over 100,000 queue durations in that period. To determine the optimal route, a node map will be developed for each park, representing the pathways throughout the park. The A* algorithm will be used to determine the shortest route between each attraction, and that value will be stored for every pair of attractions. In addition, the duration of each attraction will be stored, as longer ride times could have an effect on the overall route taken.

At runtime, the user provides the park and other relevant information. Then, the system interprets the problem as a modified Traveling Salesman Problem where the weights between nodes change depending on the previously accumulated weight (in other words, average wait times change throughout the day). This problem is then solved using a branch and bound method. Even though this is an exact solution to an NP-hard problem, the algorithm should complete in a reasonable amount of time as most parks have fewer than 30 attractions. The result of the algorithm is an ordered list of attractions, as well as the estimated duration of the round trip. This path is provided as a list as well as a line drawn on the map of the park to graphically show the route to be taken.
