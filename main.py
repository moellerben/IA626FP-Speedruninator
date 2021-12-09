from flask import Flask, render_template, request
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image
import io
import base64
from math import floor
import imageio

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Handle form
        from speedrun import get_speedrun, minutecounttodisp, getnumrides
        options = {}
        if request.form["method"] == "exact":
            options["method"] = "exact"
            routetype = "Exact"
        elif request.form["method"] == "appox":
            options["method"] = "approx"
            routetype = "Approximate"
        else:
            # Check number of rides at the park
            if getnumrides(request.form["park"]) > 15:
                options["method"] = "approx"
                routetype = "Approximate"
            else:
                options["method"] = "exact"
                routetype = "Exact"
        if request.form["walkspeed"] == "":
            walkspeed = 4
        else:
            walkspeed = float(request.form["walkspeed"])
        bestroute, attractions = get_speedrun(request.form["park"], int(request.form["starttime"]), walkspeed, options)
        mincount = int(request.form["starttime"])
        disttotal = 0
        waittotal = 0
        ridetotal = 0
        arrivaltimes = [minutecounttodisp(mincount)]
        offridetimes = [minutecounttodisp(mincount)]
        for i in range(len(bestroute["path"])-2):
            mincount += bestroute["times"][i]["distance"]
            disttotal += bestroute["times"][i]["distance"]
            arrivaltimes.append(minutecounttodisp(mincount))
            mincount += bestroute["times"][i]["wait"]
            waittotal += bestroute["times"][i]["wait"]
            mincount += bestroute["times"][i]["ride"]
            ridetotal += bestroute["times"][i]["ride"]
            offridetimes.append(minutecounttodisp(mincount))
        mincount += bestroute["times"][-1]["distance"]
        disttotal += bestroute["times"][-1]["distance"]
        arrivaltimes.append(minutecounttodisp(mincount))

        # Generate pie chart of how your day is spent
        def make_autopct(values):
            def my_autopct(pct):
                total = sum(values)
                val = int(round(pct*total/100.0))
                return '{p:.2f}%\n({h:d}:{m:02d})'.format(p=pct,h=floor(val/60),m=val%60)
            return my_autopct
        labels = ["Walking", "Queueing", "Riding"]
        sizes = [disttotal, waittotal, ridetotal]
        fig1 = Figure()
        ax1 = fig1.add_subplot(1,1,1)
        ax1.pie(sizes, labels=labels, autopct=make_autopct(sizes), startangle=90)
        ax1.axis('equal')
        out1 = io.BytesIO()
        FigureCanvas(fig1).print_png(out1)
        encoded_pie = base64.b64encode(out1.getvalue())

        # Generate map showing route
        mapbounds = {}
        mapbounds["MK"] = [[28.415214, -81.585769], [28.421979, -81.576724]]
        mapbounds["EPCOT"] = [[28.366681, -81.555524], [28.376787, -81.543440]]
        mapbounds["DHS"] = [[28.353117, -81.563629], [28.360257, -81.556983]]
        mapbounds["AK"] = [[28.353887, -81.596882], [28.366391, -81.585169]]

        bgimgfp = None
        bounds = None
        if request.form["park"] == "75ea578a-adc8-4116-a54d-dccb60765ef9": # MK
            bgimgfp = "images/MagicKingdom.png"
            bounds = mapbounds["MK"]
        elif request.form["park"] == "47f90d2c-e191-4239-a466-5892ef59a88b": # EPCOT
            bgimgfp = "images/EPCOT.png"
            bounds = mapbounds["EPCOT"]
        elif request.form["park"] == "288747d1-8b4f-4a64-867e-ea7c9b27bad8": # DHS
            bgimgfp = "images/HollywoodStudios.png"
            bounds = mapbounds["DHS"]
        elif request.form["park"] == "1c84a229-8862-4648-9c71-378ddd2c7693": # AK
            bgimgfp = "images/AnimalKingdom.png"
            bounds = mapbounds["AK"]
        if bgimgfp is not None:
            # We're in one of those parks
            bgimg = Image.open(bgimgfp)
            dpi = 100
            w,h = bgimg.size
            fig2, ax2 = plt.subplots(1,1,figsize=(w/dpi, h/dpi), dpi=dpi)
            out2 = io.BytesIO()
            #ax2 = fig2.add_subplot(1,1,1, figsize=(int(w/dpi), int(h/dpi)), dpi=dpi)
            ax2.imshow(bgimg)
            ax2.axis("off")
            #extent = ax2.get_window_extent().transformed(fig2.dpi_scale_trans.inverted())
            fig2.savefig(out2, format='png', bbox_inches="tight", pad_inches=0)
            aimg = []
            for i in range(len(bestroute["path"])-1):
                out2b = io.BytesIO()
                bgimg = Image.open(bgimgfp)
                #w,h = bgimg.size
                fig2, ax2 = plt.subplots(1,1,figsize=(w/dpi, h/dpi), dpi=dpi)
                #ax2 = fig2.add_subplot(1,1,1, figsize=(int(w/dpi), int(h/dpi)), dpi=dpi)
                ax2.imshow(bgimg)
                for j in range(i+1):
                    startlatlon = [attractions[bestroute["path"][j]]["lat"], attractions[bestroute["path"][j]]["lon"]]
                    endlatlon = [attractions[bestroute["path"][j+1]]["lat"], attractions[bestroute["path"][j+1]]["lon"]]
                    #print(f"i={i}, latlon={startlatlon}")
                    starty = (startlatlon[0]-bounds[0][0])/(bounds[1][0]-bounds[0][0])
                    startx = (startlatlon[1]-bounds[0][1])/(bounds[1][1]-bounds[0][1])
                    endy = (endlatlon[0]-bounds[0][0])/(bounds[1][0]-bounds[0][0])
                    endx = (endlatlon[1]-bounds[0][1])/(bounds[1][1]-bounds[0][1])
                    ax2.annotate("", xytext=(startx, starty), xycoords="axes fraction", xy=(endx, endy), textcoords="axes fraction", arrowprops=dict(width=3,facecolor="red",edgecolor="white"))
                ax2.axis("off")
                #extent = ax2.get_window_extent().transformed(fig2.dpi_scale_trans.inverted())
                fig2.savefig(out2b, format='png', bbox_inches="tight", pad_inches=0)
                img = Image.open(out2b)
                aimg.append(img)
            firstimg = Image.open(out2)
            out2c = io.BytesIO()
            for i in range(5):
                aimg.append(aimg[-1])
            firstimg.save(out2c, format="gif", save_all=True, append_images=aimg, duration=10*(len(aimg)+1), loop=0)
            encoded_map = base64.b64encode(out2c.getvalue())

        return render_template("route.html", bestroute=bestroute, attractions=attractions, arrivaltimes=arrivaltimes, offridetimes=offridetimes, numsteps=len(bestroute["path"]), piechart=encoded_pie.decode('utf-8'), map=encoded_map.decode('utf-8'), routetype=routetype, walkspeed=walkspeed)
    else:
        from speedrun import getParkSlugsNamesIDs
        slugs, names, ids = getParkSlugsNamesIDs()
        times = ['12 AM']
        times.extend([str(x)+" AM" for x in range(1,12)])
        times.append('12 PM')
        times.extend([str(x)+" PM" for x in range(1,12)])
        times = times[9:] + times[:9]
        minutes = [x*60 for x in range(0,24)]
        minutes = minutes[9:] + minutes[:9]
        print(times)
        return render_template("index.html", numparks=len(slugs), ids=ids, names=names, times=times, minutes=minutes)

if __name__ == "__main__":
    app.run(host='127.0.0.1', debug=True)
