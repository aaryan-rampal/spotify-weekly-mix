# %%
import pandas as pd
# %%
saved_songs_file = "saved_songs.csv"
saved_df = pd.read_csv(saved_songs_file)
saved_df.head()
# %%
# print first 5 rows of the dataframe pretty
print(saved_df.head().to_string())

# %%
sorted_df = saved_df.sort_values(by="Popularity", inplace=False)
sorted_df

# %%
sorted_df["seconds"] = sorted_df["Duration"].apply(lambda x: int(x.split(":")[0]) * 60 + int(x.split(":")[1]))
sorted_df

# %%
# plot a histogram of the seconds column
sorted_df["seconds"].hist(bins=100)

# %%
print("Shortest song:", sorted_df["seconds"].min())
print("Longest song:", sorted_df["seconds"].max())

idx_shortest = sorted_df["seconds"].idxmin()
idx_longest = sorted_df["seconds"].idxmax()
print("Shortest song:", sorted_df.loc[idx_shortest]["Title"])
print("Longest song:", sorted_df.loc[idx_longest]["Title"])
# %%
sorted_df["Release Date"] = pd.to_datetime(sorted_df["Release Date"], format="mixed")
sorted_df["Release Date"].hist(bins=100)

# %%
# group by album and count
sorted_df.groupby("Album").size().hist(bins=100)
sorted_df.groupby("Album").size().sort_values(ascending=False).head()


# %%
# artists is comma separated, so we need to split it
sorted_df["Artists"] = sorted_df["Artists"].str.split(",")

# %%
sorted_df["Popularity"].hist(bins=100)

# %%
filtered_df = sorted_df[sorted_df["Popularity"] != 0]
filtered_df.sort_values(by="Popularity", inplace=True)
filtered_df.head(50)

# %%
