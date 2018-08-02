#########################################################################################################
# TabCompare
# v1.3
# This script uses the Tableau Server Client To Compare Content on 2x Tableau Server Environments
# For more information, refer http://tableaujunkie.com
# To run the script, you must have installed Python 2.7.X or 3.3 and later.
#########################################################################################################

# import the necessary packages
import argparse
import getpass
import os
import shutil
from threading import Thread
import requests
import tableauserverclient as TSC
from wand.image import Image

#v1.3 surpress SSL certificate warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

os.environ['MAGICK_HOME'] = os.path.abspath('.')

#main program generates images from Tableau Server
def main(serverName,filepath):

    #if no site name provided then get all sites
    if args.si==None:
        all_sites = getAllSites(serverName)
        if all_sites:
            for site in all_sites:
                generateSiteImages(serverName,site,filepath)
        else:
            os._exit(1)
            return False

    #else only generate images for site matching name provided
    else:
        site = getSite(serverName)
        if site:
            generateSiteImages(serverName, site, filepath)
        else:
            os._exit(1)
            return False

def getSite(serverName):
    try:
        # Step 1: Sign in to server.
        tableau_auth = TSC.TableauAuth(args.u, password, site_id=args.si)
        server = TSC.Server(serverName)
        server.add_http_options({'verify': False})
        server.version = APIVERSION

        with server.auth.sign_in(tableau_auth):
            # query the sites
            if args.si=="":
                site = server.sites.get_by_name("Default")
            else:
                site = server.sites.get_by_name(args.si)

        return site

    except Exception as e:
        print(e.message)
        os._exit(1)
        return False

def getAllSites(serverName):
    try:
        # Step 1: Sign in to server.
        tableau_auth = TSC.TableauAuth(args.u, password, site_id="")
        server = TSC.Server(serverName)
        server.add_http_options({'verify': False})
        # The new endpoint was introduced in Version 2.4
        server.version = APIVERSION

        with server.auth.sign_in(tableau_auth):
            # query the sites
            all_sites = list(TSC.Pager(server.sites))

        return all_sites

    except Exception as e:
        print(e.message)
        os._exit(1)
        return False

def generateSiteImages(serverName, site, filepath):
    if site.name == "Default":
        site_id = ""
    else:
        site_id = site.name

    tableau_auth = TSC.TableauAuth(args.u, password, site_id=site_id)
    server = TSC.Server(serverName)
    server.add_http_options({'verify': False})
    server.version = APIVERSION
    with server.auth.sign_in(tableau_auth):
        print("signed in to " + serverName, site.name, site.content_url, site.state)
        directory = filepath + "\\" + site.id
        try:
            os.stat(directory)
        except:
            os.mkdir(directory)
        req_option = TSC.RequestOptions()
        #if workbook name passed filter on it
        if not args.wi==None:
            req_option.filter.add(TSC.Filter(TSC.RequestOptions.Field.Name,
                                             TSC.RequestOptions.Operator.Equals,
                                             args.wi))
        # get workbooks
        all_workbooks = list(TSC.Pager(server.workbooks,req_option))

        #if no workbooks returned then return
        if not all_workbooks:
            return

        #filter on project if supplied
        filtered_workbooks=[]
        if not args.pi == None:
            for workbook in all_workbooks:
                if workbook.project_name==args.pi:
                    filtered_workbooks.append(workbook)
            all_workbooks=filtered_workbooks

        # print name workbooks

        workbook_ids = []
        for workbook in all_workbooks:
            workbook_ids.append(workbook.id)
            directory = filepath + "\\" + site.id + "\\" + workbook.id
            try:
                os.stat(directory)
            except:
                os.mkdir(directory)

        # get views
        all_views = list(TSC.Pager(server.views))
        #print("\nThere are {} views on site: ".format(len(all_views)))
        #print([view.name for view in all_views])

        # filter on workbook or project if supplied
        filtered_views = []

        for view in all_views:
            if view.workbook_id in workbook_ids:
                filtered_views.append(view)
        all_views = filtered_views

        for view in all_views:
            # Step 2: Query for the view that we want an image of
            try:
                print("requesting view " + view.content_url + " from " + serverName)

                #use vizportal API to get png as support for images was only introduced in v2.5 of the REST API
                xTableauAuth = server.auth_token
                h={
                    "Cookie": "workgroup_session_id="+ xTableauAuth
                }

                siteUrl = (server.server_address + "/t/" + site.name).replace("t/Default","")
                imageUrl = siteUrl + "/views/" + view.content_url.replace("/sheets","") + ".png"
                #print (imageUrl)

                r = requests.get(imageUrl,headers = h,verify=False)

                #print r.headers.get('content-type')

                #get image using REST API v2.5+
                #server.views.populate_image(view)

                directory = filepath + "\\" + site.id + "\\" + view.workbook_id + "\\" + str(view.id) + ".png"

                if r.content != None:
                    with open(directory, "wb") as image_file:
                        print("Saving View "+ view.name + " to {0}".format(str(view.id) + ".png"))
                        image_file.write(r.content)
            except Exception as e:
                print(e.message)

def compareAllImages(filepath):

    report=args.f + "\\" + "Report.csv"
    if os.path.exists(report):
        os.remove(report)

    if args.cm:
        compare_metric = args.cm
    else:
        compare_metric='peak_signal_to_noise_ratio'


    with open(report, "w") as report_file:
        report_file.write("image_file, difference, image_on_both_servers, image_size_is_different" + '\n')

        for path, subdirs, files in os.walk(filepath + "\\serverA"):
            for name in files:
                imageA = os.path.join(path, name)
                imageB = os.path.join(path, name).replace("serverA","serverB")
                print("Comparing Images...")
                print(imageA)
                print(imageB)
                filesSizeDifferent=False
                fileExistsOnServerB=True

                if not os.path.exists(imageB):
                    fileExistsOnServerB = False
                    # image does not exist on serverB

                    # write line to output file
                    report_file.write(name + ", " + str(metric) + ", " + str(fileExistsOnServerB) + ", " + str(
                        filesSizeDifferent) + '\n')
                    continue

                try:
                    with Image(filename=imageA) as image1:
                        with Image(filename=imageB) as image2:

                            # if images are different sizes resize target image to be same as source image before comparing
                            if image1.size != image2.size:
                                filesSizeDifferent = True

                                # trim images
                                image1.trim()
                                image2.trim()


                            comparison = image1.compare(image2,compare_metric)
                            metric = comparison[1]

                            print(compare_metric, "difference:", metric)
                            if metric == 0:
                                print("The images are the same")

                            else:
                                difference = comparison[0]
                                filename=filepath + "\\differences\\" + name
                                difference.save(filename=filename)
                                print("the images are different")

                            #write line to output file
                            report_file.write(name + ", " + str(metric) + ", " + str(fileExistsOnServerB) + ", " + str(filesSizeDifferent) + '\n')

                except Exception as e:
                    #print(e.message)
                    #move onto next image
                    continue
    return True


def getAllImages():
    try:
        list_threads = []

        t = Thread(target=main, args=(args.sa, args.f + "\\serverA"))
        list_threads.append(t)
        t.start()

        t = Thread(target=main, args=(args.sb, args.f + "\\serverB"))
        list_threads.append(t)
        t.start()

        print("All threads are started, generating images From both servers")

        for t in list_threads:
            t.join()  # Wait until thread terminates its task

        return True

    except Exception as e:
        print(e.message)

def cleanFilepath(filepath):
    # clean output file directory
    print("Cleaning all files in filepath " + filepath)

    try:
        if os.path.isdir(filepath):
            shutil.rmtree(filepath)

        if not os.path.isdir(filepath):
            os.mkdir(filepath)
            os.mkdir(filepath + "\\serverA")
            os.mkdir(filepath + "\\serverB")
            os.mkdir(filepath + "\\differences")

        return True
    except Exception as e:
        print(e)

if __name__ == '__main__':
    APIVERSION = "2.3"

    parser = argparse.ArgumentParser(description='Query View Image From Server')
    parser.add_argument('--sa', required=True, help='Server A URL (the target/new version of Tableau Server)')
    parser.add_argument('--sb', required=True, help='Server B URL (the old version of Tableau Server)')
    parser.add_argument('--si', required=False, help='(optional) Site Name Filter')
    parser.add_argument('--pi', required=False, help='(optional) Project Name Filter')
    parser.add_argument('--wi', required=False, help='(optional) Workbook Name Filter')
    parser.add_argument('--cm', required=False, help="(optional) Compare metrics type. Default value: 'peak_signal_to_noise_ratio'. Possible values: 'undefined', 'absolute', 'mean_absolute', 'mean_error_per_pixel', 'mean_squared', 'normalized_cross_correlation', 'peak_absolute', 'peak_signal_to_noise_ratio', 'perceptual_hash', 'root_mean_square'")
    parser.add_argument('--u', required=True, help='Tableau Server Username')
    parser.add_argument('--p', required=False, help='(optional) Tableau Server Password. USER WILL BE PROMPTED FOR PASSWORD IF NOT PROVIDED')
    parser.add_argument('--f', required=True, help='filepath to save the image returned. EXITING FILES IN FILEPATH WILL BE DELETED')

    args = parser.parse_args()

    #prompt for password if it is not passed as a command line parameter
    if args.p:
        password = args.p
    else:
        password = getpass.getpass("Tableau Server Password For " +args.u+":")
    #password="admin"

    #Clean Filepath
    ret = cleanFilepath(args.f)

    if ret:
        #get Images from both servers
        ret = getAllImages()

    if ret:
        #Finished generating images
        #Compare the differences
        ret=compareAllImages(args.f)

    #If image comparison finished successfully then display message
    if ret:
        print("\n***********************************************************"
          "\nTabCompare completed successfully!"
          "\nPlease check TabCompare.twbx for your results."
          "\nImage differences were saved to the /differences directory."
          "\n***********************************************************")