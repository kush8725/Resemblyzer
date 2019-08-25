from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.animation import FuncAnimation
from resemblyzer import sampling_rate
from matplotlib import cm
from time import sleep, perf_counter as timer
from sys import stderr
import matplotlib.pyplot as plt
import sounddevice as sd
import numpy as np

_default_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]


def play_wav(wav, blocking=True):
    # Small bug with sounddevice.play: the audio is cut 0.5 second too early. We pad it to make up 
    # for that
    wav = np.concatenate((wav, np.zeros(sampling_rate // 2)))
    sd.play(wav, sampling_rate, blocking=blocking)


def plot_similarity_matrix(matrix, labels_a=None, labels_b=None, ax: plt.Axes=None, title=""):
    if ax is None:
        _, ax = plt.subplots()
    fig = plt.gcf()
        
    img = ax.matshow(matrix, extent=(-0.5, matrix.shape[0] - 0.5, 
                                     -0.5, matrix.shape[1] - 0.5))

    ax.xaxis.set_ticks_position("bottom")
    if labels_a is not None:
        ax.set_xticks(range(len(labels_a)))
        ax.set_xticklabels(labels_a, rotation=90)
    if labels_b is not None:
        ax.set_yticks(range(len(labels_b)))
        ax.set_yticklabels(labels_b[::-1])  # Upper origin -> reverse y axis
    ax.set_title(title)

    cax = make_axes_locatable(ax).append_axes("right", size="5%", pad=0.15)
    fig.colorbar(img, cax=cax, ticks=np.linspace(0.4, 1, 7))
    img.set_clim(0.4, 1)
    img.set_cmap("inferno")
    
    return ax
    
    
def plot_histograms(all_samples, ax=None, names=None, title=""):
    """
    Plots (possibly) overlapping histograms and their median 
    """
    if ax is None:
        _, ax = plt.subplots()
    
    for samples, color, name in zip(all_samples, _default_colors, names):
        ax.hist(samples, density=True, color=color + "80", label=name)
    ax.legend()
    ax.set_xlim(0.35, 1)
    ax.set_yticks([])
    ax.set_title(title)
        
    ylim = ax.get_ylim()
    ax.set_ylim(*ylim)      # Yeah, I know
    for samples, color in zip(all_samples, _default_colors):
        median = np.median(samples)
        ax.vlines(median, *ylim, color, "dashed")
        ax.text(median, ylim[1] * 0.15, "median", rotation=270, color=color)
    
    return ax


def interactive_diarization(similarity_dict, wav, wav_splits, x_crop=5):
    # The interval between frames is the interval between two wav splits (assumed constant)
    times = [((s.start + s.stop) / 2) / sampling_rate for s in wav_splits]
    rate = 1 / (times[1] - times[0])
    crop_range = int(np.round(x_crop * rate))

    fig, ax = plt.subplots()
    lines = [plt.plot([], [], label=name)[0] for name in similarity_dict.keys()]
    
    def init():
        ax.set_ylim(0.4, 1)
        ax.set_ylabel("Similarity")
        ax.set_xlabel("Time (seconds)")
        ax.set_title("Diarization")
        ax.legend(loc="lower right")
        return lines
    
    ticks = np.arange(0, len(wav_splits), rate)
    ref_time = timer()
    text = []
    
    def update(i):
        # Crop plot
        crop = (max(i - crop_range // 2, 0), i + crop_range // 2)
        ax.set_xlim(i - crop_range // 2, crop[1])
        crop_ticks = ticks[(crop[0] <= ticks) * (ticks <= crop[1])]
        ax.set_xticks(crop_ticks)
        ax.set_xticklabels(np.round(crop_ticks / rate).astype(np.int))

        # Plot the prediction
        similarities = [s[i] for s in similarity_dict.values()]
        best = np.argmax(similarities)
        name, similarity = list(similarity_dict.keys())[best], similarities[best]
        if similarity > 0.75:
            message = "Speaker: %s (confident)" % name
            color = _default_colors[best]
        elif similarity > 0.65:
            message = "Speaker: %s (uncertain)" % name
            color = _default_colors[best]
        else:
            message = "Unknown/No speaker"
            color = "black"
        if len(text) > 0:
            text.pop().remove()
        text.append(ax.text(i, 0.96, message, color=color, fontsize=11))
        
        # Plot data
        for line, (name, similarities) in zip(lines, similarity_dict.items()):
            line.set_data(range(crop[0], i + 1), similarities[crop[0]:i + 1])
        
        # Block to synchronize with the audio (interval is not reliable)
        current_time = timer() - ref_time
        if current_time < times[i]:
            sleep(times[i] - current_time)
        elif current_time - 0.2 > times[i]:
            print("Animation is delayed further than 200ms!", file=stderr)
        return lines 
    
    ani = FuncAnimation(fig, update, frames=len(wav_splits), init_func=init, blit=False,
                        repeat=False, interval=1)
    play_wav(wav, blocking=False)
    plt.show()


def plot_embedding_as_heatmap(embed, ax=None, title="", shape=None, color_range=(0, 0.30)):
    if ax is None:
        _, ax = plt.subplots()
    
    if shape is None:
        height = int(np.sqrt(len(embed)))
        shape = (height, -1)
    embed = embed.reshape(shape)
    
    cmap = cm.get_cmap()
    mappable = ax.imshow(embed, cmap=cmap)
    cbar = plt.colorbar(mappable, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_clim(*color_range)
    
    ax.set_xticks([]), ax.set_yticks([])
    ax.set_title(title)

